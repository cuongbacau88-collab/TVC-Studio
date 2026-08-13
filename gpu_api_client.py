"""Private server-to-server client for the Phase 4A GPU API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Iterator
from urllib.parse import quote
import requests


class GPUAPIError(Exception):
    def __init__(self, message: str, status: int = 502, code: str = "gpu_backend_error") -> None:
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


@dataclass(frozen=True)
class GPUAPIConfig:
    enabled: bool
    base_url: str
    service_token: str
    connect_timeout: float
    read_timeout: float


class GPUAPIClient:
    def __init__(self, config: GPUAPIConfig) -> None:
        self.config = config

    def _headers(self, owner_id: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.config.service_token}", "X-Owner-ID": owner_id}
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method: str, path: str, owner_id: str, *, stream: bool = False, **kwargs) -> requests.Response:
        if not self.config.enabled or not self.config.base_url or not self.config.service_token:
            raise GPUAPIError("GPU service is not configured", 503, "gpu_not_configured")
        try:
            response = requests.request(
                method, self.config.base_url.rstrip("/") + path,
                headers=self._headers(owner_id, kwargs.pop("headers", None)),
                timeout=(self.config.connect_timeout, self.config.read_timeout), stream=stream, **kwargs,
            )
        except requests.Timeout:
            raise GPUAPIError("GPU service timed out", 504, "gpu_timeout")
        except requests.RequestException:
            raise GPUAPIError("GPU service is unavailable", 502, "gpu_unavailable")
        if response.status_code >= 400:
            code, message = "gpu_backend_error", "GPU service rejected the request"
            try:
                error = response.json().get("error", {})
                code = str(error.get("code") or code)
                message = {
                    "queue_full": "GPU queue is full", "installed_not_ready": "GPU model is not ready",
                    "unavailable_insufficient_gpu": "GPU is unavailable",
                    "job_not_cancellable": "This job can no longer be cancelled",
                    "not_ready": "Output is not ready", "job_not_found": "GPU job was not found",
                }.get(code, message)
            except (ValueError, AttributeError):
                pass
            response.close()
            raise GPUAPIError(message, response.status_code, code)
        return response

    @staticmethod
    def _json(response: requests.Response) -> dict:
        try:
            value = response.json()
        except ValueError:
            response.close()
            raise GPUAPIError("GPU service returned invalid data")
        response.close()
        if not isinstance(value, dict):
            raise GPUAPIError("GPU service returned invalid data")
        return value

    def upload(self, owner_id: str, filename: str, content_type: str, source: BinaryIO) -> dict:
        value = self._json(self._request("POST", "/v1/uploads", owner_id, data=source, headers={
            "X-Filename": filename, "Content-Type": content_type,
        })).get("upload")
        if not isinstance(value, dict) or not value.get("id"):
            raise GPUAPIError("GPU service did not accept the upload")
        return value

    def submit(self, owner_id: str, client_job_id: str, image_upload_id: str,
               motion_upload_id: str, aspect_ratio: str, prompt: str) -> dict:
        payload = {
            "owner_id": owner_id, "client_job_id": client_job_id,
            "operation": "motion-transfer-video", "model_id": "wan22-animate",
            "inputs": {"image": {"upload_id": image_upload_id}, "motion": {"upload_id": motion_upload_id}},
            "parameters": {"aspect_ratio": aspect_ratio, "prompt": prompt},
        }
        return self._json(self._request("POST", "/v1/jobs", owner_id, json=payload))

    def status(self, owner_id: str, gpu_job_id: str) -> dict:
        return self._json(self._request("GET", f"/v1/jobs/{quote(gpu_job_id, safe='')}", owner_id))

    def cancel(self, owner_id: str, gpu_job_id: str) -> dict:
        return self._json(self._request("DELETE", f"/v1/jobs/{quote(gpu_job_id, safe='')}", owner_id))

    def output(self, owner_id: str, gpu_job_id: str) -> requests.Response:
        return self._request("GET", f"/v1/jobs/{quote(gpu_job_id, safe='')}/output", owner_id, stream=True)

    @staticmethod
    def stream(response: requests.Response, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        try:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk
        finally:
            response.close()
