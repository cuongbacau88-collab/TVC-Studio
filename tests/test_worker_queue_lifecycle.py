from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

try:
    import app
    DEPENDENCIES_AVAILABLE = True
except ModuleNotFoundError:
    app = None
    DEPENDENCIES_AVAILABLE = False


@unittest.skipUnless(DEPENDENCIES_AVAILABLE, "frontend dependencies are not installed")
class WorkerQueueLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.originals = {
            "BASE": app.BASE, "DATA": app.DATA, "UPLOADS": app.UPLOADS,
            "OUTPUTS": app.OUTPUTS, "DB_PATH": app.DB_PATH,
            "WORKER_UNAVAILABLE_TIMEOUT_SECONDS": app.WORKER_UNAVAILABLE_TIMEOUT_SECONDS,
            "WORKER_HEARTBEAT_TIMEOUT_SECONDS": app.WORKER_HEARTBEAT_TIMEOUT_SECONDS,
            "JOB_RENDER_TIMEOUT_SECONDS": app.JOB_RENDER_TIMEOUT_SECONDS,
        }
        app.BASE = self.root
        app.DATA = self.root / "data"
        app.UPLOADS = app.DATA / "uploads"
        app.OUTPUTS = app.DATA / "outputs"
        app.DB_PATH = app.DATA / "test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.WORKER_UNAVAILABLE_TIMEOUT_SECONDS = 30
        app.WORKER_HEARTBEAT_TIMEOUT_SECONDS = 20
        app.JOB_RENDER_TIMEOUT_SECONDS = 60
        app.init_db()
        con = app.db()
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)",
                    ("queue@example.com", "Queue", "x", 99, "user", app.now_iso()))
        self.user_id = con.execute("SELECT id FROM users WHERE email='queue@example.com'").fetchone()["id"]
        con.commit()
        con.close()

    def tearDown(self):
        for key, value in self.originals.items():
            setattr(app, key, value)
        self.temp.cleanup()

    def job(self, status="waiting", age=40):
        timestamp = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        con = app.db()
        cur = con.execute(
            """INSERT INTO jobs(user_id,model,service,aspect_ratio,quality,prompt,cost,image_path,
               video_path,status,progress,created_at,updated_at,credit_charged)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (self.user_id, "Motion", "motion_studio", "9:16", "720", "", 1, "a", "b",
             status, 0 if status == "waiting" else 70, timestamp, timestamp, 1),
        )
        job_id = cur.lastrowid
        con.execute("INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at) VALUES(?,?,?,?,?,?)",
                    (self.user_id, -1, "Tạo job", "job", job_id, timestamp))
        con.commit()
        con.close()
        return job_id

    def row(self, job_id):
        con = app.db()
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        con.close()
        return row

    def test_busy_worker_keeps_queued_job_waiting(self):
        job_id = self.job()
        app.record_worker_heartbeat("gpu-1", "busy", 999)
        self.assertEqual(0, app.recover_stale_jobs(self.user_id))
        self.assertEqual("waiting", self.row(job_id)["status"])

    def test_idle_worker_keeps_queue_and_can_claim(self):
        job_id = self.job()
        claimed = app.worker_claim(app.WORKER_TOKEN, "gpu-1")
        self.assertEqual(job_id, claimed["job"]["id"])
        self.assertEqual("running", self.row(job_id)["status"])

    def test_offline_worker_fails_queue_and_refunds_once(self):
        job_id = self.job()
        self.assertEqual(1, app.recover_stale_jobs(self.user_id))
        self.assertEqual("failed", self.row(job_id)["status"])
        self.assertEqual(0, app.recover_stale_jobs(self.user_id))
        con = app.db()
        self.assertEqual(100, con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"])
        self.assertEqual(1, con.execute("SELECT COUNT(*) c FROM credit_ledger WHERE ref_type='job_refund'").fetchone()["c"])
        con.close()

    def test_stale_heartbeat_is_offline(self):
        job_id = self.job()
        app.record_worker_heartbeat("gpu-1", "idle")
        old = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
        con = app.db()
        con.execute("UPDATE worker_heartbeats SET last_heartbeat=?", (old,))
        con.commit()
        con.close()
        self.assertEqual(1, app.recover_stale_jobs(self.user_id))
        self.assertEqual("failed", self.row(job_id)["status"])

    def test_running_job_with_fresh_matching_heartbeat_survives(self):
        job_id = self.job("running", age=30)
        app.record_worker_heartbeat("gpu-1", "busy", job_id)
        self.assertEqual(0, app.recover_stale_jobs(self.user_id))
        self.assertEqual("running", self.row(job_id)["status"])

    def test_running_job_without_matching_heartbeat_fails(self):
        job_id = self.job("running", age=30)
        app.record_worker_heartbeat("gpu-1", "busy", 999)
        self.assertEqual(1, app.recover_stale_jobs(self.user_id))
        self.assertEqual("failed", self.row(job_id)["status"])


if __name__ == "__main__":
    unittest.main()
