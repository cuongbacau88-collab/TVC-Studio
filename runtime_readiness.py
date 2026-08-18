"""Structured, read-only preflight for Railway and a future Vast GPU worker."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
WORKFLOW_MANIFEST_PATH = BASE / "workflows" / "manifest.json"
MODEL_MANIFEST_PATH = BASE / "configs" / "model_manifest.json"
CUSTOM_NODE_MANIFEST_PATH = BASE / "configs" / "comfy_custom_nodes.json"

MODEL_ENV_BY_SERVICE = {
    "motion_studio": ("MOTION_GPU_MODEL", "MOTION_STUDIO_MODELS"),
    "video_generation": ("VIDEO_MODEL",),
    "outfit_change": ("OUTFIT_MODEL",),
    "background_change": ("BACKGROUND_MODEL",),
    "image_upscale": ("UPSCALE_MODEL",),
}


def _load_json(path: Path, fallback: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return fallback
    return value if isinstance(value, dict) else fallback


def load_manifest() -> dict:
    return _load_json(WORKFLOW_MANIFEST_PATH, {"version": 2, "services": {}})


def load_model_manifest() -> dict:
    return _load_json(MODEL_MANIFEST_PATH, {"version": 1, "models": [], "aliases": {}})


def load_custom_node_manifest() -> dict:
    return _load_json(CUSTOM_NODE_MANIFEST_PATH, {"version": 1, "status": "UNKNOWN", "entries": []})


def resolve_model_id(model_id: str) -> str:
    manifest = load_model_manifest()
    aliases = manifest.get("aliases") or {}
    seen = set()
    current = model_id
    while current in aliases:
        if current in seen:
            raise ValueError("model alias cycle")
        seen.add(current)
        current = aliases[current]
    known = {item.get("model_id") for item in manifest.get("models") or []}
    if current not in known:
        raise KeyError(model_id)
    return current


def _configured_model(service_id: str) -> str:
    for name in MODEL_ENV_BY_SERVICE.get(service_id, ()):
        value = os.getenv(name, "").strip()
        if value:
            return value.split(",", 1)[0].strip()
    return ""


def _mapping_complete(mapping: dict) -> bool:
    inputs = (mapping or {}).get("inputs") or {}
    outputs = (mapping or {}).get("outputs") or {}
    return bool(inputs and outputs) and all(
        isinstance(item, dict) and item.get("node_id") is not None and item.get("field_name")
        for item in inputs.values()
    ) and all(isinstance(item, dict) and item.get("node_id") is not None for item in outputs.values())


def _torch_status() -> dict:
    if importlib.util.find_spec("torch") is None:
        return {"installed": False, "version": None, "cuda_version": None, "cuda_available": False}
    try:
        import torch
        return {
            "installed": True,
            "version": str(torch.__version__),
            "cuda_version": str(torch.version.cuda) if torch.version.cuda else None,
            "cuda_available": bool(torch.cuda.is_available()),
        }
    except Exception as exc:
        return {"installed": True, "version": None, "cuda_version": None, "cuda_available": False, "error": type(exc).__name__}


def _nvidia_status() -> dict:
    executable = shutil.which("nvidia-smi")
    result = {"available": bool(executable), "path": executable, "gpus": []}
    if not executable:
        return result
    try:
        completed = subprocess.run(
            [executable, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if completed.returncode == 0:
            for line in completed.stdout.splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) == 3:
                    result["gpus"].append({"name": parts[0], "vram_total_mb": int(parts[1]), "vram_free_mb": int(parts[2])})
        else:
            result["error"] = "nvidia-smi failed"
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        result["error"] = type(exc).__name__
    return result


def _path_status(value: str, *, writable: bool = False) -> dict:
    path = Path(value).expanduser() if value else None
    exists = bool(path and path.exists())
    return {
        "path": str(path) if path else None,
        "exists": exists,
        "writable": bool(exists and os.access(path, os.W_OK)) if writable else None,
    }


def runtime_preflight() -> dict:
    workflow_manifest = load_manifest()
    model_manifest = load_model_manifest()
    custom_nodes = load_custom_node_manifest()
    models = {item.get("model_id"): item for item in model_manifest.get("models") or []}
    services = {}
    for service_id, spec in (workflow_manifest.get("services") or {}).items():
        filename = spec.get("expected_filename")
        workflow_path = BASE / "workflows" / filename if filename else None
        present = bool(workflow_path and workflow_path.is_file())
        configured = _configured_model(service_id)
        canonical = spec.get("model_id")
        model_entry = models.get(canonical)
        expected_paths = (model_entry or {}).get("expected_paths") or []
        model_files_known = bool(expected_paths)
        model_files_present = model_files_known and all(Path(path).expanduser().is_file() for path in expected_paths)
        mapping_complete = _mapping_complete(spec.get("node_mapping") or {})
        required_nodes = spec.get("required_custom_nodes")
        custom_nodes_known = isinstance(required_nodes, list)
        node_entries = {item.get("node_id"): item for item in custom_nodes.get("entries") or []}
        missing_custom_nodes = [
            node_id for node_id in (required_nodes or [])
            if node_id not in node_entries or not node_entries[node_id].get("present")
        ]
        reasons = []
        if not present:
            reasons.append("workflow missing")
        if not configured:
            reasons.append("model missing")
        elif configured != canonical:
            reasons.append("configured model_id does not match canonical model_id")
        if not model_files_known:
            reasons.append("model weight filenames/paths UNKNOWN")
        elif not model_files_present:
            reasons.append("model files missing")
        if not custom_nodes_known:
            reasons.append("custom nodes UNKNOWN")
        elif missing_custom_nodes:
            reasons.append("required custom node missing")
        if not mapping_complete:
            reasons.append("node mapping missing")
        services[service_id] = {
            "workflow_id": spec.get("workflow_id"),
            "service_id": service_id,
            "model_id": canonical,
            "configured_model_id": configured or None,
            "input_schema": {"required": spec.get("required_inputs") or []},
            "output_type": ((spec.get("required_outputs") or [{}])[0]).get("media_type"),
            "workflow_file": filename,
            "workflow_path": str(workflow_path) if workflow_path else None,
            "workflow_exists": present,
            "node_mapping_complete": mapping_complete,
            "custom_nodes_known": custom_nodes_known,
            "missing_custom_nodes": missing_custom_nodes,
            "model_files_known": model_files_known,
            "model_files_present": model_files_present,
            "ready": not reasons,
            "reasons": reasons,
        }

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    comfyui = _path_status(os.getenv("COMFYUI_PATH", ""))
    input_dir = _path_status(os.getenv("COMFYUI_INPUT_DIR", ""), writable=True)
    output_dir = _path_status(os.getenv("COMFYUI_OUTPUT_DIR", ""), writable=True)
    disk_target = Path(os.getenv("COMFYUI_PATH", "") or BASE)
    try:
        usage = shutil.disk_usage(disk_target if disk_target.exists() else BASE)
        disk = {"path": str(disk_target if disk_target.exists() else BASE), "free_bytes": usage.free, "total_bytes": usage.total}
    except OSError:
        disk = {"path": str(disk_target), "free_bytes": None, "total_bytes": None}
    runtime = {
        "nvidia_smi": _nvidia_status(),
        "cuda": {"environment": os.getenv("CUDA_HOME") or os.getenv("CUDA_PATH"), **_torch_status()},
        "ffmpeg": {"ready": bool(ffmpeg), "path": ffmpeg},
        "ffprobe": {"ready": bool(ffprobe), "path": ffprobe},
        "comfyui": comfyui,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "disk": disk,
        "custom_nodes_manifest": {"status": custom_nodes.get("status", "UNKNOWN"), "entries": len(custom_nodes.get("entries") or [])},
    }
    runtime_ready = bool(
        runtime["nvidia_smi"]["available"]
        and runtime["cuda"]["installed"]
        and runtime["cuda"]["cuda_available"]
        and ffmpeg and ffprobe
        and comfyui["exists"]
        and input_dir["writable"]
        and output_dir["writable"]
    )
    return {
        "ready": bool(services) and all(item["ready"] for item in services.values()) and runtime_ready,
        "runtime_ready": runtime_ready,
        "runtime": runtime,
        "services": services,
    }
