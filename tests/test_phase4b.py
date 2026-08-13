import asyncio
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from fastapi import UploadFile
    from starlette.requests import Request
    import app
    APP_DEPENDENCIES_AVAILABLE = True
except ModuleNotFoundError:
    UploadFile = Request = None
    app = None
    APP_DEPENDENCIES_AVAILABLE = False

from gpu_api_client import GPUAPIClient, GPUAPIConfig, GPUAPIError


class FakeResponse:
    def __init__(self, status=200, payload=None, body=b"video", headers=None):
        self.status_code = status
        self.payload = payload or {}
        self.body = body
        self.headers = headers or {"content-type": "video/mp4"}
        self.closed = False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True

    def iter_content(self, chunk_size):
        yield self.body


class FakeGPU:
    def __init__(self):
        self.submit_calls = 0
        self.upload_calls = []
        self.status_payload = {"status": "queued"}
        self.cancel_payload = {"status": "cancelled"}
        self.output_response = FakeResponse()

    def upload(self, owner, filename, content_type, source):
        self.upload_calls.append((owner, filename, content_type, source.read()))
        return {"id": f"upload-{len(self.upload_calls)}"}

    def submit(self, owner, client_job_id, image_id, motion_id, aspect, prompt):
        self.submit_calls += 1
        return {"id": "gpu-job-1", "status": "queued", "duplicate": self.submit_calls > 1}

    def status(self, owner, job_id):
        return self.status_payload

    def cancel(self, owner, job_id):
        return self.cancel_payload

    def output(self, owner, job_id):
        return self.output_response

    @staticmethod
    def stream(response):
        yield from response.iter_content(1024)


@unittest.skipUnless(APP_DEPENDENCIES_AVAILABLE, "frontend dependencies are not installed")
class Phase4BTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.originals = {
            "BASE": app.BASE, "DATA": app.DATA, "UPLOADS": app.UPLOADS, "OUTPUTS": app.OUTPUTS,
            "DB_PATH": app.DB_PATH, "gpu_api": app.gpu_api,
            "GPU_BACKEND_ENABLED": app.GPU_BACKEND_ENABLED,
        }
        app.BASE = self.root
        app.DATA = self.root / "data"
        app.UPLOADS = app.DATA / "uploads"
        app.OUTPUTS = app.DATA / "outputs"
        app.DB_PATH = app.DATA / "test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.GPU_BACKEND_ENABLED = True
        app.gpu_api = FakeGPU()
        app.init_db()
        con = app.db()
        con.execute("""INSERT INTO users(email,name,password_hash,credits,role,created_at)
                       VALUES('user@example.com','User','x',5,'user',?)""", (app.now_iso(),))
        self.user_id = con.execute("SELECT id FROM users WHERE email='user@example.com'").fetchone()["id"]
        con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES('sess',?,?)",
                    (self.user_id, "2999-01-01T00:00:00+00:00"))
        con.commit(); con.close()

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        self.temp.cleanup()

    def request(self):
        return Request({"type": "http", "method": "GET", "path": "/",
                        "headers": [(b"cookie", b"mh_session=sess")]})

    @staticmethod
    def uploads():
        return (
            UploadFile(filename="person.png", file=io.BytesIO(b"image"),
                       headers={"content-type": "image/png"}),
            UploadFile(filename="motion.mp4", file=io.BytesIO(b"video"),
                       headers={"content-type": "video/mp4"}),
        )

    def submit(self, key="stable-key"):
        image, motion = self.uploads()
        user = {"id": self.user_id}
        return asyncio.run(app.create_gpu_job(user, image, motion, "Wan Animate 2", "9:16", "", key))

    def test_idempotent_retry_and_exactly_once_credit_deduction(self):
        first = self.submit()
        second = self.submit()
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        con = app.db()
        self.assertEqual(1, con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"])
        self.assertEqual(4, con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"])
        self.assertEqual(1, con.execute("SELECT COUNT(*) c FROM credit_ledger WHERE ref_type='job'").fetchone()["c"])
        con.close()
        self.assertEqual(1, app.gpu_api.submit_calls)
        self.assertEqual(2, len(app.gpu_api.upload_calls))

    def test_refund_once_on_terminal_failure(self):
        result = self.submit()
        app.apply_gpu_status(self.user_id, result["job_id"], {"status": "failed", "error": {"message": "failed"}})
        app.apply_gpu_status(self.user_id, result["job_id"], {"status": "failed", "error": {"message": "failed"}})
        con = app.db()
        self.assertEqual(5, con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"])
        self.assertEqual(1, con.execute("SELECT COUNT(*) c FROM credit_ledger WHERE ref_type='job_refund'").fetchone()["c"])
        con.close()

    def test_progress_polling(self):
        result = self.submit()
        app.gpu_api.status_payload = {"status": "running"}
        app.refresh_gpu_jobs(self.user_id)
        con = app.db()
        row = con.execute("SELECT status,progress FROM jobs WHERE id=?", (result["job_id"],)).fetchone()
        con.close()
        self.assertEqual(("running", 50), (row["status"], row["progress"]))

    def test_cancellation_and_owner_isolation(self):
        result = self.submit()
        response = app.cancel_customer_job(result["job_id"], self.request())
        self.assertEqual("cancelled", response["status"])
        con = app.db()
        self.assertEqual(5, con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"])
        con.execute("""INSERT INTO users(email,name,password_hash,credits,role,created_at)
                       VALUES('other@example.com','Other','x',1,'user',?)""", (app.now_iso(),))
        other = con.execute("SELECT id FROM users WHERE email='other@example.com'").fetchone()["id"]
        con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES('other',?,?)",
                    (other, "2999-01-01T00:00:00+00:00"))
        con.commit(); con.close()
        other_request = Request({"type": "http", "method": "DELETE", "path": "/",
                                 "headers": [(b"cookie", b"mh_session=other")]})
        with self.assertRaises(Exception) as raised:
            app.cancel_customer_job(result["job_id"], other_request)
        self.assertEqual(404, raised.exception.status_code)

    def test_output_proxy_and_ownership(self):
        result = self.submit()
        app.apply_gpu_status(self.user_id, result["job_id"], {"status": "succeeded"})
        response = app.job_output(result["job_id"], self.request())
        self.assertEqual("video/mp4", response.media_type)
        con = app.db()
        con.execute("""INSERT INTO users(email,name,password_hash,credits,role,created_at)
                       VALUES('other@example.com','Other','x',1,'user',?)""", (app.now_iso(),))
        other = con.execute("SELECT id FROM users WHERE email='other@example.com'").fetchone()["id"]
        con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES('other',?,?)",
                    (other, "2999-01-01T00:00:00+00:00"))
        con.commit(); con.close()
        other_request = Request({"type": "http", "method": "GET", "path": "/",
                                 "headers": [(b"cookie", b"mh_session=other")]})
        with self.assertRaises(Exception) as raised:
            app.job_output(result["job_id"], other_request)
        self.assertEqual(403, raised.exception.status_code)

    def test_feature_flag_preserves_legacy_worker(self):
        app.GPU_BACKEND_ENABLED = False
        con = app.db()
        cur = con.execute("""INSERT INTO jobs(user_id,model,aspect_ratio,quality,prompt,cost,image_path,
                           video_path,status,progress,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (self.user_id, "legacy", "9:16", "720", "", 1, "a", "b",
                           "waiting", 0, app.now_iso(), app.now_iso()))
        con.commit(); con.close()
        claimed = app.worker_claim(app.WORKER_TOKEN)
        self.assertEqual(cur.lastrowid, claimed["job"]["id"])


class GPUClientTests(unittest.TestCase):
    def config(self, enabled=True):
        return GPUAPIConfig(enabled, "https://gpu.invalid", "super-secret-token", 1, 2)

    @patch("gpu_api_client.requests.request")
    def test_upload_forwarding_and_private_token(self, request_mock):
        request_mock.return_value = FakeResponse(payload={"upload": {"id": "asset-1"}})
        result = GPUAPIClient(self.config()).upload("42", "image.png", "image/png", io.BytesIO(b"data"))
        self.assertEqual("asset-1", result["id"])
        kwargs = request_mock.call_args.kwargs
        self.assertEqual("Bearer super-secret-token", kwargs["headers"]["Authorization"])
        self.assertEqual("42", kwargs["headers"]["X-Owner-ID"])
        self.assertEqual((1, 2), kwargs["timeout"])

    @patch("gpu_api_client.requests.request")
    def test_token_and_raw_backend_error_never_reach_mapped_error(self, request_mock):
        request_mock.return_value = FakeResponse(500, {"error": {
            "code": "unknown", "message": "super-secret-token / internal/path"
        }})
        with self.assertRaises(GPUAPIError) as raised:
            GPUAPIClient(self.config()).status("42", "job")
        self.assertNotIn("super-secret-token", raised.exception.message)
        self.assertNotIn("internal/path", raised.exception.message)

    def test_disabled_feature_flag_makes_no_request(self):
        with patch("gpu_api_client.requests.request") as request_mock:
            with self.assertRaises(GPUAPIError) as raised:
                GPUAPIClient(self.config(False)).status("42", "job")
            self.assertEqual("gpu_not_configured", raised.exception.code)
            request_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
