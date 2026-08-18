import io
import os
import unittest
from unittest.mock import patch

import video_upscale_pipeline
from service_registry import SERVICES
from service_worker_adapters import WorkerAdapterError, normalize_status


class Config:
    def __init__(self, configured=True):
        self.configured = configured
        self.target_short_side = 1080


class OriginalResponse:
    def __init__(self):
        self.raw = io.BytesIO(b"original-video")
        self.headers = {"content-type": "video/mp4"}
        self.closed = False

    def close(self):
        self.closed = True


class OriginalAdapter:
    def __init__(self):
        self.response = OriginalResponse()

    def result(self, job_id):
        return self.response


class UpscaleAdapter:
    def __init__(self, configured=True):
        self.video_config = Config(configured)
        self.payload = None
        self.status_payload = {"status": "processing", "progress": 42}

    def submit(self, client_job_id, payload, files):
        self.payload = payload
        self.source = files["source_video"][1].read()
        return {"job_id": "hd-1", "status": "queued"}

    def status(self, job_id):
        if isinstance(self.status_payload, Exception):
            raise self.status_payload
        return self.status_payload


class App:
    def __init__(self, configured=True):
        self.video_upscale_adapter = UpscaleAdapter(configured)
        self.service_adapters = {"video_generation": OriginalAdapter()}


class VideoUpscalePipelineTests(unittest.TestCase):
    def row(self):
        return {
            "id": 5, "user_id": 7, "service": "video_generation",
            "worker_job_id": "render-1", "client_job_id": "client-1",
            "video_upscale_attempted": 0, "output_path": None, "gpu_job_id": None,
        }

    def test_disabled_pipeline_keeps_original_done(self):
        value = video_upscale_pipeline.start(App(False), self.row())
        self.assertEqual({"status": "done", "progress": 100}, value)

    def test_submit_preserves_video_properties_without_usage_charge(self):
        app = App()
        value = video_upscale_pipeline.start(app, self.row())
        self.assertEqual("upscaling", value["status"])
        self.assertEqual("hd-1", value["upscale_job_id"])
        self.assertEqual(b"original-video", app.video_upscale_adapter.source)
        self.assertEqual(1080, app.video_upscale_adapter.payload["target_short_side"])
        for key in ("preserve_aspect_ratio", "preserve_fps", "preserve_duration", "preserve_audio"):
            self.assertTrue(app.video_upscale_adapter.payload[key])
        self.assertNotIn("cost", app.video_upscale_adapter.payload)

    def test_failure_falls_back_to_original(self):
        app = App()
        app.video_upscale_adapter.status_payload = WorkerAdapterError("seed failed")
        value = video_upscale_pipeline.poll(app, {"video_upscale_job_id": "hd-1"})
        self.assertEqual("done", value["status"])
        self.assertEqual("failed", value["upscale_status"])
        self.assertIn("seed failed", value["upscale_error"])
    def test_models_are_read_from_environment(self):
        values = {
            "VIDEO_MODEL": "wan22-start-end", "OUTFIT_MODEL": "flux-2-klein-4b",
            "BACKGROUND_MODEL": "flux-2-klein-4b", "UPSCALE_MODEL": "real-esrgan",
        }
        with patch.dict(os.environ, values, clear=False):
            self.assertEqual("wan22-start-end", SERVICES["video_generation"].model)
            self.assertEqual("flux-2-klein-4b", SERVICES["outfit_change"].model)
            self.assertEqual("flux-2-klein-4b", SERVICES["background_change"].model)
            self.assertEqual("real-esrgan", SERVICES["image_upscale"].model)

    def test_upscale_worker_status_is_normalized(self):
        self.assertEqual("processing", normalize_status("in_progress"))


if __name__ == "__main__":
    unittest.main()
