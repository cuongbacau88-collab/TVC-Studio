"""Configuration registry for GPU-backed AI services."""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ServiceDefinition:
    key: str
    title: str
    operation: str
    worker_prefix: str
    output_kind: str
    priority: int
    usage_cost: int | None
    model_env: str
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...] = ()

    @property
    def is_free(self) -> bool:
        return self.usage_cost == 0

    @property
    def model(self) -> str:
        return os.getenv(self.model_env, "").strip()

def _optional_nonnegative_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


SERVICES = {
    "video_generation": ServiceDefinition(
        "video_generation", "AI Tạo Video", "video_generation", "VIDEO",
        "video", 100, _optional_nonnegative_int("VIDEO_USAGE_COST"),
        "VIDEO_MODEL", ("prompt",), ("reference_image",),
    ),
    "outfit_change": ServiceDefinition(
        "outfit_change", "AI Đổi Trang Phục", "outfit_change", "OUTFIT",
        "image", 10, 0, "OUTFIT_MODEL", ("character_image", "outfit_image"), ("prompt",),
    ),
    "background_change": ServiceDefinition(
        "background_change", "AI Đổi Bối Cảnh", "background_change", "BACKGROUND",
        "image", 10, 0, "BACKGROUND_MODEL", ("source_image",), ("background_image", "prompt"),
    ),
    "image_upscale": ServiceDefinition(
        "image_upscale", "AI Nâng Cấp Ảnh", "image_upscale", "UPSCALE",
        "image", 10, 0, "UPSCALE_MODEL", ("source_image",), ("scale", "restore_face"),
    ),
}


MOTION_MODELS = [value.strip() for value in os.getenv("MOTION_STUDIO_MODELS", "").split(",") if value.strip()]
BACKGROUND_MASK_MODEL = os.getenv("BACKGROUND_MASK_MODEL", "").strip()

def get_service(key: str) -> ServiceDefinition:
    try:
        return SERVICES[key]
    except KeyError as exc:
        raise KeyError("Dịch vụ không tồn tại") from exc


PUBLIC_SERVICE_CONFIG = {
    "video_generation": {
        "aspect_ratios": ["auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
        "durations": [
            value.strip() for value in os.getenv("VIDEO_ALLOWED_DURATIONS", "").split(",")
            if value.strip()
        ],
    },
    "outfit_change": {},
    "background_change": {},
    "image_upscale": {
        "scales": [
            int(value) for value in os.getenv("UPSCALE_ALLOWED_SCALES", "2,4").split(",")
            if value.strip().isdigit() and int(value) in {2, 4}
        ],
        "face_restore_supported": os.getenv(
            "UPSCALE_FACE_RESTORE_SUPPORTED", "false"
        ).lower() in {"1", "true", "yes", "on"},
    },
}
