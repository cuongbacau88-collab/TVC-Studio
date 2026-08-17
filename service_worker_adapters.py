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


class ProductionUpscaleAdapter(ServiceWorkerAdapter):
    """Adapter for the authenticated production GPU API upload/job contract."""

    def _owner_request(self, method: str, path: str, owner_id: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["X-Owner-ID"] = str(owner_id)
        return self._request(method, path, headers=headers, **kwargs)

    def submit_upscale(self, owner_id: str, client_job_id: str,
                       files: dict[str, tuple[str, BinaryIO, str]]) -> dict:
        source = files.get("source_image")
        if source is None:
            raise WorkerAdapterError("Thiếu ảnh cần nâng cấp", 400, "source_image_required")
        filename, stream, media_type = source
        upload = self._json(self._owner_request(
            "POST", "/v1/uploads", owner_id, data=stream,
            headers={"X-Filename": filename, "Content-Type": media_type},
        )).get("upload")
        upload_id = str(upload.get("id") or "") if isinstance(upload, dict) else ""
        if not upload_id:
            raise WorkerAdapterError("Máy chủ xử lý chưa xác nhận file tải lên")
        value = self._json(self._owner_request(
            "POST", "/v1/jobs", owner_id, json={
                "owner_id": str(owner_id),
                "client_job_id": client_job_id,
                "operation": "image-upscale-restoration",
                "model_id": "realesrgan",
                "inputs": {"image": {"upload_id": upload_id}},
                "parameters": {},
            },
        ))
        job_id = str(value.get("id") or "")
        if not job_id:
            raise WorkerAdapterError("Máy chủ xử lý chưa xác nhận job")
        value["job_id"] = job_id
        value["status"] = normalize_status(value.get("status"))
        return value

    def status_upscale(self, worker_job_id: str, owner_id: str) -> dict:
        value = self._json(self._owner_request(
            "GET", f"/v1/jobs/{quote(worker_job_id, safe='')}", owner_id,
        ))
        value["status"] = normalize_status(value.get("status"))
        return value

    def cancel_upscale(self, worker_job_id: str, owner_id: str) -> dict:
        value = self._json(self._owner_request(
            "DELETE", f"/v1/jobs/{quote(worker_job_id, safe='')}", owner_id,
        ))
        value["status"] = normalize_status(value.get("status"))
        return value

    def result_upscale(self, worker_job_id: str, owner_id: str) -> requests.Response:
        return self._owner_request(
            "GET", f"/v1/jobs/{quote(worker_job_id, safe='')}/output", owner_id, stream=True,
        )

    def health(self) -> dict:
        if not self.config.configured:
            return {"configured": False, "online": False, "status": "not_configured"}
        try:
            value = self._json(self._request("GET", "/health/ready"))
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
        adapter_class = ProductionUpscaleAdapter if key == "image_upscale" else ServiceWorkerAdapter
        result[key] = adapter_class(service, WorkerConfig(
            os.getenv(f"{prefix}_WORKER_URL", "").strip(),
            os.getenv(f"{prefix}_WORKER_TOKEN", "").strip(),
            timeout,
        ))
    return result
