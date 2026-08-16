import asyncio
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException, UploadFile
from starlette.requests import Request

import app
import service_routes
from service_registry import SERVICES
from storage_backend import LocalStorage


class MockServiceJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.originals = {
            "BASE": app.BASE, "DATA": app.DATA, "UPLOADS": app.UPLOADS,
            "OUTPUTS": app.OUTPUTS, "DB_PATH": app.DB_PATH, "storage": app.storage,
            "RENDER_MODE": app.RENDER_MODE,
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
        (self.root / "static" / "videos").mkdir(parents=True)
        app.storage = LocalStorage(app.DATA)
        app.RENDER_MODE = "mock"
        app.WORKER_UNAVAILABLE_TIMEOUT_SECONDS = 60
        app.WORKER_HEARTBEAT_TIMEOUT_SECONDS = 60
        app.JOB_RENDER_TIMEOUT_SECONDS = 60
        app.init_db()
        con = app.db()
        con.execute(
            "INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)",
            ("mock@example.com", "Mock User", "x", 100, "user", app.now_iso()),
        )
        self.user_id = con.execute(
            "SELECT id FROM users WHERE email='mock@example.com'"
        ).fetchone()["id"]
        con.execute(
            "INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
            ("mock-session", self.user_id, "2999-01-01T00:00:00+00:00"),
        )
        con.commit()
        con.close()

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        self.temp.cleanup()

    def request(self, method="POST"):
        return Request({
            "type": "http", "method": method, "path": "/",
            "headers": [(b"cookie", b"mh_session=mock-session")],
        })

    @staticmethod
    def image(name="image.png", content=b"independent-image-input"):
        return UploadFile(
            filename=name, file=io.BytesIO(content),
            headers={"content-type": "image/png"},
        )

    @staticmethod
    def video(name="motion.mp4", content=b"independent-motion-input"):
        return UploadFile(
            filename=name, file=io.BytesIO(content),
            headers={"content-type": "video/mp4"},
        )

    def credits(self):
        con = app.db()
        value = con.execute(
            "SELECT credits FROM users WHERE id=?", (self.user_id,)
        ).fetchone()["credits"]
        con.close()
        return value

    def row(self, job_id):
        con = app.db()
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        con.close()
        return row

    def create_service(self, service, key):
        kwargs = dict(
            service_key=service, request=self.request(), prompt="",
            aspect_ratio="", duration="", scale="", restore_face=False,
            request_key=key, creation_method="reference_images",
            reference_purposes="[]", reference_images=[], reference_videos=[],
            first_frame=None, last_frame=None, language="vi",
            reference_image=None, character_image=None, outfit_image=None,
            source_image=None, background_image=None,
        )
        if service == "video_generation":
            kwargs.update(prompt="Create a new test video", aspect_ratio="9:16",
                          duration=app.MOCK_VIDEO_DURATION)
        elif service == "outfit_change":
            kwargs.update(character_image=self.image("character.png"),
                          outfit_image=self.image("outfit.png", b"outfit-input"))
        elif service == "background_change":
            kwargs.update(source_image=self.image("source.png"),
                          prompt="A test studio background")
        elif service == "image_upscale":
            kwargs.update(source_image=self.image("source.png"), scale="2")
        return asyncio.run(service_routes.create_job(**kwargs))

    def test_all_four_service_endpoints_create_and_mock_complete_with_correct_output_kind(self):
        expected = {
            "video_generation": ".mp4",
            "outfit_change": ".png",
            "background_change": ".png",
            "image_upscale": ".png",
        }
        for service, suffix in expected.items():
            with self.subTest(service=service):
                created = self.create_service(service, "create-" + service)
                self.assertEqual("waiting", created["status"])
                completed = app.process_mock_job(created["id"])
                self.assertEqual("done", completed["status"])
                self.assertEqual("mock_completed", completed["worker_status"])
                output = app.BASE / completed["output_path"]
                self.assertTrue(output.is_file())
                self.assertEqual(suffix, output.suffix)
                self.assertEqual(
                    "video" if suffix == ".mp4" else "image",
                    SERVICES[service].output_kind,
                )

    def test_motion_endpoint_charges_once_and_mock_completes(self):
        created = asyncio.run(app.create_job(
            self.request(), self.image("character.png"), self.video(),
            model="Wan Animate 2", aspect_ratio="9:16", prompt="",
            request_key="motion-once",
        ))
        self.assertEqual(99, self.credits())
        completed = app.process_mock_job(created["job_id"])
        self.assertEqual("done", completed["status"])
        self.assertEqual(".mp4", Path(completed["output_path"]).suffix)
        duplicate = asyncio.run(app.create_job(
            self.request(), self.image("character.png"), self.video(),
            model="Wan Animate 2", aspect_ratio="9:16", prompt="",
            request_key="motion-once",
        ))
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(99, self.credits())

    def test_worker_mode_without_gpu_times_out_fails_and_refunds_once(self):
        app.RENDER_MODE = "worker"
        created = asyncio.run(app.create_job(
            self.request(), self.image("character.png"), self.video(),
            model="Wan Animate 2", aspect_ratio="9:16", prompt="",
            request_key="worker-absent",
        ))
        self.assertEqual(99, self.credits())
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        con = app.db()
        con.execute("UPDATE jobs SET updated_at=? WHERE id=?",
                    (stale_time.isoformat(), created["job_id"]))
        con.commit()
        con.close()
        reference = datetime.now(timezone.utc)
        failed_public = service_routes.get_job(
            "motion_studio", created["job_id"], self.request("GET")
        )
        self.assertEqual("failed", failed_public["status"])
        failed = self.row(created["job_id"])
        self.assertEqual("failed", failed["status"])
        self.assertIsNone(failed["output_path"])
        self.assertIn("GPU worker", failed["error"])
        self.assertEqual(100, self.credits())
        self.assertEqual(0, app.recover_stale_jobs(self.user_id, reference))
        self.assertEqual(100, self.credits())

    def test_invalid_form_does_not_create_job_or_charge(self):
        before = self.credits()
        with self.assertRaises(HTTPException):
            asyncio.run(service_routes.create_job(
                service_key="outfit_change", request=self.request(), prompt="",
                aspect_ratio="", duration="", scale="", restore_face=False,
                request_key="invalid-outfit", creation_method="reference_images",
                reference_purposes="[]", reference_images=[], reference_videos=[],
                first_frame=None, last_frame=None, language="vi",
                reference_image=None, character_image=None, outfit_image=None,
                source_image=None, background_image=None,
            ))
        con = app.db()
        count = con.execute(
            "SELECT COUNT(*) count FROM jobs WHERE user_id=?", (self.user_id,)
        ).fetchone()["count"]
        con.close()
        self.assertEqual(0, count)
        self.assertEqual(before, self.credits())

    def test_service_duplicate_request_does_not_duplicate_history_or_charge(self):
        first = self.create_service("outfit_change", "same-service-key")
        second = self.create_service("outfit_change", "same-service-key")
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["id"], second["id"])
        con = app.db()
        count = con.execute(
            "SELECT COUNT(*) count FROM jobs WHERE user_id=? AND service='outfit_change'",
            (self.user_id,),
        ).fetchone()["count"]
        con.close()
        self.assertEqual(1, count)

    def create_first_last(self, key, first=True, last=True):
        return asyncio.run(service_routes.create_job(
            service_key="video_generation", request=self.request(),
            prompt="Chuyển cảnh tự nhiên", aspect_ratio="9:16",
            duration=app.MOCK_VIDEO_DURATION, scale="", restore_face=False,
            request_key=key, creation_method="first_last",
            reference_purposes="[]", reference_images=[], reference_videos=[],
            first_frame=self.image("start.png", b"start-image") if first else None,
            last_frame=self.image("end.png", b"end-image") if last else None,
            language="vi", reference_image=None, character_image=None,
            outfit_image=None, source_image=None, background_image=None,
        ))

    def test_first_last_uses_independent_payload_fields_and_mock_completes(self):
        created = self.create_first_last("first-last-mock")
        row = self.row(created["id"])
        payload = __import__("json").loads(row["input_json"])
        self.assertNotEqual(payload["files"]["first_frame"], payload["files"]["last_frame"])
        self.assertIn("first_frame", payload["file_roles"])
        self.assertIn("last_frame", payload["file_roles"])
        completed = app.process_mock_job(created["id"])
        self.assertEqual("done", completed["status"])
        self.assertEqual(99, self.credits())

    def test_first_last_missing_either_image_does_not_create_or_charge(self):
        for key, first, last in (("missing-start", False, True), ("missing-end", True, False), ("missing-both", False, False)):
            with self.subTest(key=key), self.assertRaises(HTTPException):
                self.create_first_last(key, first, last)
        con = app.db()
        count = con.execute("SELECT COUNT(*) count FROM jobs WHERE user_id=?", (self.user_id,)).fetchone()["count"]
        con.close()
        self.assertEqual(0, count)
        self.assertEqual(100, self.credits())

    def test_first_last_worker_offline_is_queued_without_fake_output(self):
        app.RENDER_MODE = "worker"
        created = self.create_first_last("first-last-offline")
        row = self.row(created["id"])
        self.assertEqual("waiting", row["status"])
        self.assertIsNone(row["worker_job_id"])
        self.assertIsNone(row["output_path"])
        self.assertEqual(99, self.credits())

    def test_catalog_exposes_mock_services_without_real_worker_configuration(self):
        catalog = {item["key"]: item for item in service_routes.catalog()}
        self.assertEqual(set(SERVICES), set(catalog))
        self.assertTrue(all(item["configured"] for item in catalog.values()))
        self.assertEqual(["5", "10"], catalog["video_generation"]["durations"])
        self.assertEqual(1, catalog["video_generation"]["usage"])


    def test_history_maps_all_services_and_frontend_submit_is_locked(self):
        history_js = (Path(app.__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
        service_js = (Path(app.__file__).parent / "static" / "service.js").read_text(encoding="utf-8")
        for title in (
            "AI Motion Studio", "AI Video Creator", "AI Đổi Trang Phục",
            "AI Đổi Bối Cảnh", "AI Nâng Cấp Ảnh",
        ):
            self.assertIn(title, history_js)
        self.assertIn("jobOutputExtension", history_js)
        self.assertIn("if(submitting)return", service_js)
        self.assertIn("submitButton').disabled=true", service_js)
        self.assertIn("/api/services/${key}/jobs", service_js)

if __name__ == "__main__":
    unittest.main()
