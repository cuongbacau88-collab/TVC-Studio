import asyncio
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException, UploadFile
from starlette.requests import Request

import app


class RenderLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.originals = {
            "BASE": app.BASE, "DATA": app.DATA, "UPLOADS": app.UPLOADS,
            "OUTPUTS": app.OUTPUTS, "DB_PATH": app.DB_PATH,
            "JOB_QUEUE_TIMEOUT_SECONDS": app.JOB_QUEUE_TIMEOUT_SECONDS,
            "JOB_RENDER_TIMEOUT_SECONDS": app.JOB_RENDER_TIMEOUT_SECONDS,
        }
        app.BASE = self.root
        app.DATA = self.root / "data"
        app.UPLOADS = app.DATA / "uploads"
        app.OUTPUTS = app.DATA / "outputs"
        app.DB_PATH = app.DATA / "test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        (self.root / "static" / "videos").mkdir(parents=True)
        app.JOB_QUEUE_TIMEOUT_SECONDS = 60
        app.JOB_RENDER_TIMEOUT_SECONDS = 60
        app.init_db()
        con = app.db()
        con.execute(
            "INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)",
            ("render@example.com", "Render", "x", 99, "user", app.now_iso()),
        )
        self.user_id = con.execute(
            "SELECT id FROM users WHERE email='render@example.com'"
        ).fetchone()["id"]
        con.execute(
            "INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
            ("render-session", self.user_id, "2999-01-01T00:00:00+00:00"),
        )
        con.commit()
        con.close()

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        self.temp.cleanup()

    def request(self):
        return Request({
            "type": "http", "method": "GET", "path": "/api/jobs",
            "headers": [(b"cookie", b"mh_session=render-session")],
        })

    def create_job(self, status="running", progress=70, updated_at=None):
        job_dir = app.UPLOADS / "fixture"
        job_dir.mkdir(exist_ok=True)
        image = job_dir / "character.png"
        motion = job_dir / "motion.mp4"
        image.write_bytes(b"image-input")
        motion.write_bytes(b"motion-input-content")
        timestamp = updated_at or app.now_iso()
        con = app.db()
        cursor = con.execute(
            """INSERT INTO jobs(
               user_id,model,service,aspect_ratio,quality,prompt,cost,image_path,video_path,
               status,progress,created_at,updated_at,credit_charged
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (self.user_id, "Motion", "motion_studio", "9:16", "720", "", 1,
             str(image.relative_to(app.BASE)), str(motion.relative_to(app.BASE)),
             status, progress, timestamp, timestamp, 1),
        )
        job_id = cursor.lastrowid
        con.execute(
            "INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at) VALUES(?,?,?,?,?,?)",
            (self.user_id, -1, "Tạo job", "job", job_id, timestamp),
        )
        con.commit()
        con.close()
        return job_id, motion

    def row(self, job_id):
        con = app.db()
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        con.close()
        return row

    def credits(self):
        con = app.db()
        value = con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"]
        con.close()
        return value

    def test_stuck_job_is_failed_and_refunded_once_after_timeout(self):
        stale = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        job_id, _ = self.create_job(updated_at=stale)
        reference = datetime.now(timezone.utc)
        self.assertEqual(1, app.recover_stale_jobs(self.user_id, reference))
        self.assertEqual("failed", self.row(job_id)["status"])
        self.assertIn("không phản hồi", self.row(job_id)["error"])
        self.assertEqual(100, self.credits())
        self.assertEqual(0, app.recover_stale_jobs(self.user_id, reference))
        self.assertEqual(100, self.credits())

    def test_motion_input_cannot_be_uploaded_as_output(self):
        job_id, motion = self.create_job()
        upload = UploadFile(filename="result.mp4", file=io.BytesIO(motion.read_bytes()))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(app.worker_complete(job_id, upload, app.WORKER_TOKEN))
        self.assertEqual(422, raised.exception.status_code)
        self.assertEqual("failed", self.row(job_id)["status"])
        self.assertIsNone(self.row(job_id)["output_path"])

    def test_demo_asset_cannot_be_uploaded_as_output(self):
        demo = self.root / "static" / "videos" / "card_motion.mp4"
        demo.write_bytes(b"website-demo-video")
        job_id, _ = self.create_job()
        upload = UploadFile(filename="result.mp4", file=io.BytesIO(demo.read_bytes()))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(app.worker_complete(job_id, upload, app.WORKER_TOKEN))
        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("demo", self.row(job_id)["error"])
        self.assertIsNone(self.row(job_id)["output_path"])

    def test_valid_mock_output_completes_and_history_uses_only_real_output(self):
        job_id, _ = self.create_job()
        upload = UploadFile(filename="result.mp4", file=io.BytesIO(b"independent-mock-render-output"))
        result = asyncio.run(app.worker_complete(job_id, upload, app.WORKER_TOKEN))
        self.assertTrue(result["ok"])
        row = self.row(job_id)
        self.assertEqual("done", row["status"])
        self.assertEqual(100, row["progress"])
        self.assertTrue((app.BASE / row["output_path"]).is_file())
        history = {item["id"]: item for item in app.my_jobs(self.request())}
        self.assertEqual(1, history[job_id]["has_output"])

    def test_pending_rendering_and_failed_history_never_expose_output(self):
        pending, _ = self.create_job(status="waiting", progress=0)
        rendering, _ = self.create_job(status="running", progress=70)
        failed, _ = self.create_job(status="running", progress=70)
        app.fail_job_once(failed, "Render worker crashed")
        con = app.db()
        con.execute("UPDATE jobs SET output_path='data/outputs/fake.mp4' WHERE id IN (?,?,?)",
                    (pending, rendering, failed))
        con.commit()
        con.close()
        history = {item["id"]: item for item in app.my_jobs(self.request())}
        self.assertEqual(0, history[pending]["has_output"])
        self.assertEqual(0, history[rendering]["has_output"])
        self.assertEqual(0, history[failed]["has_output"])
        self.assertEqual("Render worker crashed", history[failed]["error"])

    def test_failure_refund_is_idempotent(self):
        job_id, _ = self.create_job()
        self.assertTrue(app.fail_job_once(job_id, "first failure"))
        self.assertFalse(app.fail_job_once(job_id, "duplicate callback"))
        self.assertEqual(100, self.credits())
        con = app.db()
        count = con.execute(
            "SELECT COUNT(*) c FROM credit_ledger WHERE ref_type='job_refund' AND ref_id=?",
            (job_id,),
        ).fetchone()["c"]
        con.close()
        self.assertEqual(1, count)


if __name__ == "__main__":
    unittest.main()
