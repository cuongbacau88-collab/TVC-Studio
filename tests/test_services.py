import asyncio
import io
import os
from pathlib import Path
import tempfile
import unittest

from fastapi import UploadFile
from starlette.requests import Request

import app
import service_routes
from service_worker_adapters import normalize_status, WorkerAdapterError
from storage_backend import LocalStorage


class Config:
    def __init__(self, configured=True):
        self.configured = configured


class FakeAdapter:
    def __init__(self, configured=True):
        self.config = Config(configured)
        self.submits = 0
        self.status_value = {"status": "queued", "progress": 0}
        self.cancelled = False

    def submit(self, client_job_id, payload, files):
        self.submits += 1
        return {"job_id": "worker-1", "status": "queued"}

    def status(self, worker_job_id):
        return self.status_value

    def cancel(self, worker_job_id):
        self.cancelled = True
        self.status_value = {"status": "cancelled", "progress": 100}
        return self.status_value

    def result(self, worker_job_id):
        raise AssertionError("not used")

    def health(self):
        return {"configured": self.config.configured, "online": self.config.configured}


class ServiceAPITests(unittest.TestCase):
    def setUp(self):
        self.original_outfit_model = os.environ.get("OUTFIT_MODEL")
        os.environ["OUTFIT_MODEL"] = "flux-2-klein-4b"
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.originals = {
            "BASE": app.BASE, "DATA": app.DATA, "UPLOADS": app.UPLOADS,
            "OUTPUTS": app.OUTPUTS, "DB_PATH": app.DB_PATH, "storage": app.storage,
            "service_adapters": app.service_adapters,
        }
        app.BASE = self.root
        app.DATA = self.root / "data"
        app.UPLOADS = app.DATA / "uploads"
        app.OUTPUTS = app.DATA / "outputs"
        app.DB_PATH = app.DATA / "test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.storage = LocalStorage(app.DATA)
        self.adapter = FakeAdapter()
        app.service_adapters = {key: FakeAdapter(False) for key in app.service_adapters}
        app.service_adapters["outfit_change"] = self.adapter
        app.init_db()
        con = app.db()
        con.execute(
            """INSERT INTO users(email,name,password_hash,credits,role,created_at)
               VALUES('service@example.com','Service User','x',3,'user',?)""",
            (app.now_iso(),)
        )
        self.user_id = con.execute("SELECT id FROM users WHERE email='service@example.com'").fetchone()["id"]
        con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES('service-session',?,?)",
                    (self.user_id, "2999-01-01T00:00:00+00:00"))
        con.commit()
        con.close()

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        if self.original_outfit_model is None:
            os.environ.pop("OUTFIT_MODEL", None)
        else:
            os.environ["OUTFIT_MODEL"] = self.original_outfit_model
        self.temp.cleanup()

    def request(self):
        return Request({
            "type": "http", "method": "POST", "path": "/",
            "headers": [(b"cookie", b"mh_session=service-session")]
        })

    @staticmethod
    def image(name="image.png", content=b"image"):
        return UploadFile(filename=name, file=io.BytesIO(content), headers={"content-type": "image/png"})

    def submit_outfit(self, key="same-key", first=None, second=None):
        return asyncio.run(service_routes.create_job(
            "outfit_change", self.request(), prompt="", aspect_ratio="", duration="",
            scale="", restore_face=False, request_key=key, reference_image=None,
            character_image=first or self.image("person.png"),
            outfit_image=second or self.image("outfit.png"),
            source_image=None, background_image=None,
        ))

    def test_create_free_job_and_duplicate_are_idempotent(self):
        first = self.submit_outfit()
        duplicate = self.submit_outfit()
        self.assertFalse(first["duplicate"])
        self.assertTrue(first["free"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(1, self.adapter.submits)
        con = app.db()
        self.assertEqual(1, con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"])
        self.assertEqual(3, con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"])
        con.close()

    def test_upload_validation_removes_unaccepted_job(self):
        with self.assertRaises(Exception) as raised:
            self.submit_outfit(first=self.image("person.exe"))
        self.assertEqual(400, raised.exception.status_code)
        con = app.db()
        self.assertEqual(0, con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"])
        con.close()

    def test_offline_worker_rejects_without_creating_job(self):
        app.service_adapters["outfit_change"] = FakeAdapter(False)
        with self.assertRaises(Exception) as raised:
            self.submit_outfit()
        self.assertEqual(503, raised.exception.status_code)
        self.assertIn("chưa kết nối", raised.exception.detail)
        con = app.db()
        self.assertEqual(0, con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"])
        con.close()

    def test_failure_normalization_and_refund_is_once(self):
        job = self.submit_outfit()
        self.adapter.status_value = {"status": "error", "error": "GPU failed"}
        first = service_routes.refresh_job(self.user_id, job["id"])
        second = service_routes.refresh_job(self.user_id, job["id"])
        self.assertEqual("failed", first["status"])
        self.assertEqual("failed", second["status"])
        con = app.db()
        self.assertEqual(0, con.execute(
            "SELECT COUNT(*) c FROM credit_ledger WHERE ref_type='job_refund'"
        ).fetchone()["c"])
        con.close()

    def test_background_requires_reference_or_prompt(self):
        with self.assertRaises(Exception) as raised:
            service_routes.validate_request(
                "background_change", "", "", "", "", False,
                {"source_image": self.image(), "background_image": None}
            )
        self.assertEqual(400, raised.exception.status_code)


class StatusNormalizationTests(unittest.TestCase):
    def test_worker_statuses_are_normalized(self):
        expected = {
            "pending": "queued", "running": "processing", "in_progress": "processing",
            "succeeded": "completed", "error": "failed", "canceled": "cancelled",
        }
        self.assertEqual(expected, {value: normalize_status(value) for value in expected})


if __name__ == "__main__":
    unittest.main()
