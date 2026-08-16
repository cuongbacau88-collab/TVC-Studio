"""Deterministic local fixtures for explicit RENDER_MODE=mock tests."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


SERVICE_COLORS = {
    "motion_studio": "#6d28d9",
    "video_generation": "#0369a1",
    "outfit_change": "#be185d",
    "background_change": "#15803d",
    "image_upscale": "#b45309",
}


def render_mock_fixture(service: str, job_id: int, output_path: Path) -> bool:
    """Create an output independent from every uploaded input and website demo asset."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    color = SERVICE_COLORS.get(service, "#334155")
    if output_path.suffix.lower() == ".png":
        image = Image.new("RGB", (640, 640), color)
        draw = ImageDraw.Draw(image)
        draw.text((32, 32), f"TVC TEST OUTPUT\n{service}\njob #{job_id}", fill="white")
        image.save(output_path, "PNG")
        return output_path.is_file() and output_path.stat().st_size > 0

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Mock video cần ffmpeg nhưng máy chủ chưa cài đặt")
    completed = subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i",
            f"color=c={color}:s=320x180:d=1:r=24",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path),
        ],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "Không tạo được mock video")[-1000:])
    return output_path.is_file() and output_path.stat().st_size > 0
