import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import runtime_readiness


ROOT = Path(__file__).resolve().parents[1]


class WorkflowAndModelManifestTests(unittest.TestCase):
    def test_five_service_workflow_entries_have_full_schema_and_no_fake_ready(self):
        manifest = runtime_readiness.load_manifest()
        expected = {"motion_studio", "video_generation", "outfit_change", "background_change", "image_upscale"}
        self.assertEqual(expected, set(manifest["services"]))
        required = {
            "workflow_id", "service_id", "model_id", "expected_filename", "workflow_type",
            "required_inputs", "required_outputs", "required_models", "required_custom_nodes",
            "present", "ready", "readiness_reason", "node_mapping",
        }
        for service_id, item in manifest["services"].items():
            self.assertTrue(required.issubset(item))
            self.assertEqual(service_id, item["service_id"])
            self.assertFalse(item["present"])
            self.assertFalse(item["ready"])

    def test_canonical_ids_are_unique_and_known_aliases_resolve(self):
        manifest = runtime_readiness.load_model_manifest()
        ids = [item["model_id"] for item in manifest["models"]]
        self.assertEqual(len(ids), len(set(ids)))
        for model_id in ids:
            self.assertEqual(model_id, runtime_readiness.resolve_model_id(model_id))
        for alias, target in manifest.get("aliases", {}).items():
            self.assertEqual(target, runtime_readiness.resolve_model_id(alias))
        for unsupported in ("seedvr2", "minimax_h3", "wan22_ti2v"):
            with self.assertRaises(KeyError):
                runtime_readiness.resolve_model_id(unsupported)

    def test_motion_and_five_service_model_contracts_match_source_configuration(self):
        services = runtime_readiness.load_manifest()["services"]
        self.assertEqual("wan-animate-2", services["motion_studio"]["model_id"])
        self.assertEqual("wan_animate_2_api.json", services["motion_studio"]["expected_filename"])
        self.assertEqual("wan22-start-end", services["video_generation"]["model_id"])
        self.assertEqual("flux-2-klein-4b", services["outfit_change"]["model_id"])
        self.assertEqual("flux-2-klein-4b", services["background_change"]["model_id"])
        self.assertEqual("real-esrgan", services["image_upscale"]["model_id"])
        env = (ROOT / ".env.example").read_text(encoding="utf-8")
        for literal in ("MOTION_GPU_MODEL=wan-animate-2", "VIDEO_MODEL=wan22-start-end",
                        "OUTFIT_MODEL=flux-2-klein-4b", "BACKGROUND_MODEL=flux-2-klein-4b",
                        "UPSCALE_MODEL=real-esrgan", "VIDEO_UPSCALE_MODEL=seedvr2-3b-fp8"):
            self.assertIn(literal, env)

    def test_unknown_component_weights_and_sources_are_not_fabricated(self):
        manifest = runtime_readiness.load_model_manifest()
        self.assertTrue(all(not item["present"] and not item["verified"] for item in manifest["models"]))
        self.assertTrue(all(item["expected_weight_files"] == [] for item in manifest["models"]))
        self.assertTrue(all(item["expected_paths"] == [] for item in manifest["models"]))
        self.assertTrue(all(value == "UNKNOWN" for value in manifest["component_weights"].values()))
        nodes = runtime_readiness.load_custom_node_manifest()
        self.assertEqual("UNKNOWN", nodes["status"])
        self.assertEqual([], nodes["entries"])


class GPUPreflightTests(unittest.TestCase):
    def test_missing_workflow_model_and_null_node_mapping_prevent_dispatch_readiness(self):
        empty_env = {name: "" for names in runtime_readiness.MODEL_ENV_BY_SERVICE.values() for name in names}
        with patch.dict(os.environ, empty_env, clear=False), patch("runtime_readiness.shutil.which", return_value=None), patch("runtime_readiness.importlib.util.find_spec", return_value=None):
            report = runtime_readiness.runtime_preflight()
        self.assertFalse(report["ready"])
        for item in report["services"].values():
            self.assertFalse(item["ready"])
            self.assertIn("workflow missing", item["reasons"])
            self.assertIn("model missing", item["reasons"])
            self.assertIn("node mapping missing", item["reasons"])

    def test_required_custom_node_missing_prevents_ready(self):
        spec = {
            "services": {"motion_studio": {
                "workflow_id": "real", "service_id": "motion_studio", "model_id": "wan-animate-2",
                "expected_filename": "real.json", "required_inputs": ["character_image"],
                "required_outputs": [{"media_type": "video"}], "required_custom_nodes": ["node-pack"],
                "node_mapping": {"inputs": {"character_image": {"node_id": "1", "field_name": "image"}},
                                 "outputs": {"video": {"node_id": "2"}}},
            }}
        }
        models = {"models": [{"model_id": "wan-animate-2", "expected_paths": ["/weights/model.safetensors"]}], "aliases": {}}
        with patch("runtime_readiness.load_manifest", return_value=spec), patch("runtime_readiness.load_model_manifest", return_value=models), patch("runtime_readiness.load_custom_node_manifest", return_value={"entries": []}), patch.object(Path, "is_file", return_value=True), patch.dict(os.environ, {"MOTION_GPU_MODEL": "wan-animate-2"}, clear=False):
            report = runtime_readiness.runtime_preflight()
        item = report["services"]["motion_studio"]
        self.assertFalse(item["ready"])
        self.assertEqual(["node-pack"], item["missing_custom_nodes"])
        self.assertIn("required custom node missing", item["reasons"])

    def test_preflight_has_structured_gpu_runtime_fields_without_real_gpu(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {
                "COMFYUI_PATH": temp, "COMFYUI_INPUT_DIR": temp, "COMFYUI_OUTPUT_DIR": temp,
            }, clear=False), patch("runtime_readiness.shutil.which", side_effect=lambda name: f"/usr/bin/{name}"), patch("runtime_readiness._nvidia_status", return_value={"available": True, "path": "/usr/bin/nvidia-smi", "gpus": [{"name": "mock", "vram_total_mb": 1, "vram_free_mb": 1}]}), patch("runtime_readiness._torch_status", return_value={"installed": True, "version": "test", "cuda_version": "test", "cuda_available": True}):
                report = runtime_readiness.runtime_preflight()
        runtime = report["runtime"]
        self.assertTrue(report["runtime_ready"])
        for key in ("nvidia_smi", "cuda", "ffmpeg", "ffprobe", "comfyui", "input_dir", "output_dir", "disk", "custom_nodes_manifest"):
            self.assertIn(key, runtime)


class InstallAndDownloadPlanTests(unittest.TestCase):
    def test_download_dry_run_never_downloads_and_fails_for_missing_sources(self):
        script = ROOT / "scripts" / "download_models.py"
        source = script.read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("urlopen", source)
        result = subprocess.run([sys.executable, str(script), "--dry-run"], capture_output=True, text=True, timeout=10)
        self.assertEqual(1, result.returncode)
        self.assertIn("FAIL: download source missing", result.stdout)
        self.assertIn("total_size_bytes: UNKNOWN", result.stdout)

    def test_install_plan_contains_all_ordered_steps(self):
        plan = (ROOT / "docs" / "vast_gpu_install_plan.md").read_text(encoding="utf-8")
        headings = [
            "## 1. Vast instance requirements", "## 2. Ubuntu, CUDA, and Python requirements",
            "## 3. Clone the repository", "## 4. Install Python dependencies",
            "## 5. Install ComfyUI", "## 6. Install custom nodes", "## 7. Download models",
            "## 8. Place weights at verified paths", "## 9. Copy workflows", "## 10. Run preflight",
            "## 11. Start ComfyUI", "## 12. Start the GPU worker",
            "## 13. Register the worker with Railway", "## 14. Run smoke tests",
            "## 15. Run one real test job",
        ]
        positions = [plan.index(value) for value in headings]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
