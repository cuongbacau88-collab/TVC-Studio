"""Uniform adapters for independently deployed GPU service workers."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

import requests

from service_registry import SERVICES, ServiceDefinition


STATUS_MAP = {
    "queued": "queued", "waiting": "queued", "pending": "queued",
    "processing": "processing", "running": "processing", "in_progress": "processing",
    "completed": "completed", "complete": "completed", "done": "completed",
    "succeeded": "completed", "success": "completed",
    "failed": "failed", "error": "failed",
    "cancelled": "cancelled", "canceled": "cancelled",
}


class WorkerAdapterError(Exception):
    def __init__(self, message: str, status: int = 502, code: str = "worker_error"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


@dataclass(frozen=True)
class WorkerConfig:
    url: str
    token: str
    request_timeout: float

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)


class ServiceWorkerAdapter:
    def __init__(self, service: ServiceDefinition, config: WorkerConfig):
        self.service, self.config = service, config

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        if not self.config.configured:
            raise WorkerAdapterError(
                "Dịch vụ chưa kết nối máy chủ xử lý", 503, "worker_not_configured"
            )
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.config.token}"
        try:
            response = requests.request(
                method, self.config.url.rstrip("/") + path,
                headers=headers, timeout=self.config.request_timeout, **kwargs
            )
        except requests.Timeout as exc:
            raise WorkerAdapterError("Máy chủ xử lý phản hồi quá thời gian", 504, "worker_timeout") from exc
        except requests.RequestException as exc:
            raise WorkerAdapterError("Dịch vụ chưa kết nối máy chủ xử lý", 503, "worker_offline") from exc
        if response.status_code >= 400:
            response.close()
            raise WorkerAdapterError("Máy chủ xử lý từ chối yêu cầu", 502, "worker_rejected")
        return response

    @staticmethod
    def _json(response: requests.Response) -> dict:
        try:
            value = response.json()
        except ValueError as exc:
            raise WorkerAdapterError("Máy chủ xử lý trả dữ liệu không hợp lệ") from exc
        finally:
            response.close()
        if not isinstance(value, dict):
            raise WorkerAdapterError("Máy chủ xử lý trả dữ liệu không hợp lệ")
        return value

    def submit(self, client_job_id: str, payload: dict, files: dict[str, tuple[str, BinaryIO, str]]) -> dict:
        opened = {
            name: (filename, source, media_type)
            for name, (filename, source, media_type) in files.items()
        }
        response = self._request(
            "POST", "/v1/jobs", data={
                "client_job_id": client_job_id,
                "model": self.service.model,
                "operation": self.service.operation,
                "priority": str(self.service.priority),
                "payload": __import__("json").dumps(payload, ensure_ascii=False),
            }, files=opened,
        )
        value = self._json(response)
        job_id = str(value.get("job_id") or value.get("id") or "")
        if not job_id:
            raise WorkerAdapterError("Máy chủ xử lý chưa xác nhận job")
        value["job_id"] = job_id
        value["status"] = normalize_status(value.get("status"))
        return value

    def status(self, worker_job_id: str) -> dict:
        value = self._json(self._request("GET", f"/v1/jobs/{quote(worker_job_id, safe='')}"))
        value["status"] = normalize_status(value.get("status"))
        return value

    def cancel(self, worker_job_id: str) -> dict:
        value = self._json(self._request("DELETE", f"/v1/jobs/{quote(worker_job_id, safe='')}"))
        value["status"] = normalize_status(value.get("status"))
        return value

    def result(self, worker_job_id: str) -> requests.Response:
        return self._request("GET", f"/v1/jobs/{quote(worker_job_id, safe='')}/result", stream=True)

    def health(self) -> dict:
        if not self.config.configured:
            return {"configured": False, "online": False, "status": "not_configured"}
        try:
            value = self._json(self._request("GET", "/health"))
            return {"configured": True, "online": True, "status": "online", "detail": value}
        except WorkerAdapterError as error:
            return {"configured": True, "online": False, "status": "offline", "error": error.code}


def normalize_status(value) -> str:
    return STATUS_MAP.get(str(value or "").strip().lower(), "queued")


@dataclass(frozen=True)
class VideoUpscaleConfig:
    enabled: bool
    url: str
    token: str
    model: str
    target_short_side: int
    timeout: float
    priority: int = 100

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.url and self.token and self.model)


def build_video_upscale_adapter() -> ServiceWorkerAdapter:
    enabled = os.getenv("VIDEO_UPSCALE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    definition = ServiceDefinition(
        "video_upscale", "Nâng cấp video HD", "video_upscale", "VIDEO_UPSCALE",
        "video", 100, 0, "VIDEO_UPSCALE_MODEL", ("source_video",),
    )
    config = VideoUpscaleConfig(
        enabled, os.getenv("VIDEO_UPSCALE_WORKER_URL", "").strip(),
        os.getenv("VIDEO_UPSCALE_WORKER_TOKEN", "").strip(),
        os.getenv("VIDEO_UPSCALE_MODEL", "").strip(),
        int(os.getenv("VIDEO_UPSCALE_TARGET_SHORT_SIDE", "1080") or "1080"),
        float(os.getenv("VIDEO_UPSCALE_TIMEOUT", os.getenv("WORKER_REQUEST_TIMEOUT", "30")) or "30"),
    )
    adapter = ServiceWorkerAdapter(definition, WorkerConfig(config.url, config.token, config.timeout))
    adapter.video_config = config
    return adapter

def build_adapters() -> dict[str, ServiceWorkerAdapter]:
    timeout = float(os.getenv("WORKER_REQUEST_TIMEOUT", "30") or "30")
    result = {}
    for key, service in SERVICES.items():
        prefix = service.worker_prefix
        result[key] = ServiceWorkerAdapter(service, WorkerConfig(
            os.getenv(f"{prefix}_WORKER_URL", "").strip(),
            os.getenv(f"{prefix}_WORKER_TOKEN", "").strip(),
            timeout,
        ))
    return result
