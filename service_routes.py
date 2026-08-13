"""HTTP routes for GPU-backed services other than Motion Studio."""
from __future__ import annotations

import json
import mimetypes
import secrets
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from service_registry import SERVICES, PUBLIC_SERVICE_CONFIG, get_service
from service_worker_adapters import WorkerAdapterError, normalize_status

import video_upscale_pipeline
router = APIRouter()
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
PROTECTED_PROMPTS = {
    "outfit_change": {
        "vi": "Chỉ thay trang phục của nhân vật trong ảnh gốc theo ảnh trang phục tham chiếu. Giữ nguyên khuôn mặt, danh tính, kiểu tóc, tông da, tỷ lệ cơ thể, tư thế, góc máy, ánh sáng và bối cảnh. Không lấy khuôn mặt, cơ thể hoặc tư thế từ ảnh trang phục.",
        "en": "Only replace the original character's clothing using the outfit reference. Preserve the face, identity, hairstyle, skin tone, body proportions, pose, camera angle, lighting, and background. Do not copy the face, body, or pose from the outfit image.",
    },
    "background_change": {
        "vi": "Chỉ thay bối cảnh của ảnh gốc theo ảnh tham chiếu hoặc mô tả. Giữ nguyên tuyệt đối khuôn mặt, danh tính, kiểu tóc, trang phục, cơ thể, tư thế, góc máy và bố cục nhân vật. Ghép cảnh tự nhiên, giữ viền tóc sạch và không làm da bị ám màu theo nền.",
        "en": "Only replace the original image background using the reference image or description. Strictly preserve the face, identity, hairstyle, clothing, body, pose, camera angle, and character composition. Blend naturally, keep clean hair edges, and prevent background color spill on skin.",
    },
}

def protected_prompt(service_key: str, language: str, user_prompt: str):
    system = PROTECTED_PROMPTS.get(service_key, {}).get(language) or PROTECTED_PROMPTS.get(service_key, {}).get("vi")
    return system, user_prompt or system or ""


def core():
    import app
    return app


def worker_error(error: WorkerAdapterError):
    status = error.status if error.status in {400, 404, 409, 413, 415, 422, 502, 503, 504} else 502
    return HTTPException(status, error.message)


def public_job(row):
    data = dict(row)
    return {
        "id": data["id"], "service": data["service"], "title": data["model"],
        "status": data["status"], "progress": data["progress"], "error": data["error"],
        "usage": data["cost"], "usage_unit": "lượt", "free": data["cost"] == 0,
        "created_at": data["created_at"], "updated_at": data["updated_at"],
        "has_result": data["status"] == "done", "can_cancel": data["status"] == "waiting",
        "upscale_fallback": bool(data.get("video_upscale_error")),
    }


def refresh_job(user_id: int, job_id: int):
    app = core()
    con = app.db()
    row = con.execute(
        "SELECT * FROM jobs WHERE id=? AND user_id=? AND worker_job_id IS NOT NULL",
        (job_id, user_id)
    ).fetchone()
    con.close()
    if not row or row["status"] not in {"waiting", "running", "upscaling"}:
        return dict(row) if row else None
    if row["status"] == "upscaling":
        return video_upscale_pipeline.persist(app, job_id, video_upscale_pipeline.poll(app, dict(row)))
    try:
        payload = app.service_adapters[row["service"]].status(row["worker_job_id"])
    except WorkerAdapterError:
        return dict(row)
    normalized = normalize_status(payload.get("status"))
    local_status = {
        "queued": "waiting", "processing": "running", "completed": "done",
        "failed": "failed", "cancelled": "cancelled",
    }[normalized]
    defaults = {"waiting": 0, "running": 50, "done": 100, "failed": 100, "cancelled": 100}
    try:
        progress = max(0, min(100, int(payload.get("progress", defaults[local_status]))))
    except (TypeError, ValueError):
        progress = defaults[local_status]
    error_text = str(payload.get("error") or "")[:1000] or None
    if local_status == "done" and row["service"] == "video_generation":
        con = app.db(); con.execute("UPDATE jobs SET original_output_available=1 WHERE id=?", (job_id,)); con.commit(); con.close()
        return video_upscale_pipeline.persist(app, job_id, video_upscale_pipeline.start(app, dict(row)))
    con = app.db()
    try:
        con.execute("BEGIN IMMEDIATE")
        current = con.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, user_id)).fetchone()
        if not current:
            con.rollback()
            return None
        if local_status in {"failed", "cancelled"} and current["credit_charged"] and not current["credit_refunded"]:
            con.execute("UPDATE users SET credits=credits+? WHERE id=?", (current["cost"], user_id))
            con.execute(
                """INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (user_id, current["cost"], f"Hoàn lượt job #{job_id}", "job_refund", job_id, app.now_iso())
            )
            con.execute("UPDATE jobs SET credit_refunded=1 WHERE id=?", (job_id,))
        con.execute(
            """UPDATE jobs SET status=?,progress=?,worker_status=?,error=?,updated_at=?
               WHERE id=? AND user_id=?""",
            (local_status, progress, normalized, error_text, app.now_iso(), job_id, user_id)
        )
        con.commit()
        return dict(con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    finally:
        con.close()


@router.get("/api/services")
def catalog():
    app = core()
    return [{
        "key": key, "title": definition.title, "output_kind": definition.output_kind,
        "free": definition.is_free, "usage": definition.usage_cost, "usage_unit": "lượt",
        "configured": app.service_adapters[key].config.configured and bool(definition.model),
        "model_configured": bool(definition.model),
        "poll_interval": app.WORKER_POLL_INTERVAL,
        "priority": "high" if definition.priority >= 100 else "idle",
        **PUBLIC_SERVICE_CONFIG.get(key, {}),
    } for key, definition in SERVICES.items()]


def validate_request(service_key, prompt, aspect_ratio, duration, scale, restore_face, uploads):
    if service_key == "video_generation":
        if not prompt:
            raise HTTPException(400, "Hãy nhập prompt")
        if aspect_ratio not in {"9:16", "16:9", "1:1"}:
            raise HTTPException(400, "Tỷ lệ không hợp lệ")
        durations = PUBLIC_SERVICE_CONFIG[service_key]["durations"]
        if not durations:
            raise HTTPException(503, "Model chưa được cấu hình thời lượng hỗ trợ")
        if duration not in durations:
            raise HTTPException(400, "Thời lượng không hợp lệ")
    elif service_key == "outfit_change":
        if not uploads["character_image"] or not uploads["outfit_image"]:
            raise HTTPException(400, "Cần ảnh nhân vật và ảnh trang phục")
    elif service_key == "background_change":
        if not uploads["source_image"]:
            raise HTTPException(400, "Cần ảnh gốc")
        if not uploads["background_image"] and not prompt:
            raise HTTPException(400, "Cần ảnh bối cảnh hoặc prompt mô tả")
    elif service_key == "image_upscale":
        if not uploads["source_image"]:
            raise HTTPException(400, "Cần ảnh muốn nâng cấp")
        try:
            scale_value = int(scale)
        except (TypeError, ValueError):
            raise HTTPException(400, "Mức phóng đại không hợp lệ")
        if scale_value not in PUBLIC_SERVICE_CONFIG[service_key]["scales"]:
            raise HTTPException(400, "Mức phóng đại không hợp lệ")
        if restore_face and not PUBLIC_SERVICE_CONFIG[service_key]["face_restore_supported"]:
            raise HTTPException(400, "Worker chưa hỗ trợ phục hồi khuôn mặt")


@router.post("/api/services/{service_key}/jobs")
async def create_job(
    service_key: str, request: Request, prompt: str = Form(""),
    aspect_ratio: str = Form(""), duration: str = Form(""), scale: str = Form(""),
    restore_face: bool = Form(False), request_key: str = Form(""),
    language: str = Form("vi"),
    reference_image: UploadFile | None = File(None),
    character_image: UploadFile | None = File(None),
    outfit_image: UploadFile | None = File(None),
    source_image: UploadFile | None = File(None),
    background_image: UploadFile | None = File(None),
):
    app = core()
    user = app.current_user(request)
    try:
        service = get_service(service_key)
    except KeyError:
        raise HTTPException(404, "Dịch vụ không tồn tại")
    adapter = app.service_adapters[service_key]
    if not adapter.config.configured:
        raise HTTPException(503, "Dịch vụ chưa kết nối máy chủ xử lý")
    if not service.model:
        raise HTTPException(503, "Dịch vụ chưa được cấu hình model")
    if service_key == "background_change" and not __import__("service_registry").BACKGROUND_MASK_MODEL:
        raise HTTPException(503, "Dịch vụ chưa được cấu hình model tạo mask")
    if service.usage_cost is None:
        raise HTTPException(503, "Dịch vụ chưa được cấu hình mức lượt sử dụng")
    prompt = prompt.strip()[:2000]
    language = "en" if language == "en" else "vi"
    system_prompt, prompt = protected_prompt(service_key, language, prompt)
    uploads = {
        "reference_image": reference_image, "character_image": character_image,
        "outfit_image": outfit_image, "source_image": source_image,
        "background_image": background_image,
    }
    validate_request(service_key, prompt, aspect_ratio, duration, scale, restore_face, uploads)
    request_key = (request_key or secrets.token_urlsafe(24)).strip()[:128]

    con = app.db()
    try:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute(
            "SELECT * FROM jobs WHERE user_id=? AND service=? AND request_key=?",
            (user["id"], service_key, request_key)
        ).fetchone()
        if existing:
            con.commit()
            return {**public_job(existing), "duplicate": True}
        if service.usage_cost:
            balance = con.execute("SELECT credits FROM users WHERE id=?", (user["id"],)).fetchone()
            reserved = con.execute(
                "SELECT COALESCE(SUM(cost),0) total FROM jobs WHERE user_id=? AND credit_reserved=1",
                (user["id"],)
            ).fetchone()["total"]
            if not balance or balance["credits"] - reserved < service.usage_cost:
                raise HTTPException(402, "Không đủ lượt")
        client_job_id = f"tvc-{user['id']}-{service_key}-{request_key}"
        cursor = con.execute(
            """INSERT INTO jobs(
               user_id,model,service,aspect_ratio,quality,prompt,cost,image_path,video_path,
               status,progress,created_at,updated_at,request_key,client_job_id,credit_reserved,
               input_json,priority
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user["id"], service.title, service_key, aspect_ratio or "n/a", "worker",
             prompt, service.usage_cost, "", "", "uploading", 0, app.now_iso(), app.now_iso(),
             request_key, client_job_id, 1 if service.usage_cost else 0, "{}", service.priority)
        )
        job_id = cursor.lastrowid
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    prefix = f"service-inputs/{user['id']}/{job_id}"
    stored, opened = {}, {}
    try:
        for name, upload in uploads.items():
            if not upload:
                continue
            ext = Path(upload.filename or "").suffix.lower()
            path = app.storage.path(f"{prefix}/{name}{ext}")
            path.parent.mkdir(parents=True, exist_ok=True)
            await app.save_upload(upload, path, IMAGE_EXTENSIONS, app.MAX_IMAGE_MB)
            stored[name] = f"{prefix}/{name}{ext}"
            opened[name] = (
                Path(upload.filename or f"{name}{ext}").name, path.open("rb"),
                upload.content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
        payload = {
            "prompt": prompt, "aspect_ratio": aspect_ratio, "duration": duration,
            "scale": int(scale) if scale else None, "restore_face": restore_face,
            "model": service.model,
            "mask_model": __import__("service_registry").BACKGROUND_MASK_MODEL if service_key == "background_change" else None,
            "system_prompt": system_prompt,
            "language": language,
        }
        accepted = adapter.submit(client_job_id, payload, opened)
    except WorkerAdapterError as error:
        app.storage.delete_prefix(prefix)
        cleanup = app.db()
        cleanup.execute("DELETE FROM jobs WHERE id=? AND credit_charged=0", (job_id,))
        cleanup.commit(); cleanup.close()
        raise worker_error(error)
    except Exception:
        app.storage.delete_prefix(prefix)
        cleanup = app.db()
        cleanup.execute("DELETE FROM jobs WHERE id=? AND credit_charged=0", (job_id,))
        cleanup.commit(); cleanup.close()
        raise
    finally:
        for _, source, _ in opened.values():
            source.close()

    con = app.db()
    try:
        con.execute("BEGIN IMMEDIATE")
        if service.usage_cost:
            charged = con.execute(
                "UPDATE users SET credits=credits-? WHERE id=? AND credits>=?",
                (service.usage_cost, user["id"], service.usage_cost)
            )
            if charged.rowcount != 1:
                raise HTTPException(402, "Không đủ lượt")
            con.execute(
                """INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (user["id"], -service.usage_cost, f"Sử dụng {service.title} #{job_id}", "job", job_id, app.now_iso())
            )
        con.execute(
            """UPDATE jobs SET image_path=?,video_path=?,input_json=?,worker_job_id=?,
               worker_status=?,status='waiting',credit_reserved=0,credit_charged=?,updated_at=?
               WHERE id=?""",
            (stored.get("source_image") or stored.get("character_image") or stored.get("reference_image") or "",
             stored.get("outfit_image") or stored.get("background_image") or "",
             json.dumps({"files": stored, **payload}, ensure_ascii=False), accepted["job_id"],
             accepted["status"], 1 if service.usage_cost else 0, app.now_iso(), job_id)
        )
        con.commit()
        return {**public_job(con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()), "duplicate": False}
    except Exception:
        con.rollback()
        try:
            adapter.cancel(accepted["job_id"])
        except WorkerAdapterError:
            pass
        raise
    finally:
        con.close()


@router.get("/api/services/{service_key}/jobs/{job_id}")
def get_job(service_key: str, job_id: int, request: Request):
    app = core()
    user = app.current_user(request)
    row = refresh_job(user["id"], job_id)
    if not row or row["service"] != service_key:
        raise HTTPException(404, "Không tìm thấy job")
    return public_job(row)


@router.get("/api/services/{service_key}/jobs/{job_id}/result")
def result(service_key: str, job_id: int, request: Request):
    app = core()
    user = app.current_user(request)
    con = app.db()
    row = con.execute("SELECT * FROM jobs WHERE id=? AND user_id=? AND service=?", (job_id, user["id"], service_key)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Không tìm thấy job")
    if row["status"] != "done":
        raise HTTPException(409, "Kết quả chưa sẵn sàng")
    try:
        upstream = video_upscale_pipeline.result_response(app, row) if service_key == "video_generation" else None
        if upstream is None:
            upstream = app.service_adapters[service_key].result(row["worker_job_id"])
    except WorkerAdapterError as error:
        raise worker_error(error)
    media_type = upstream.headers.get("content-type", "application/octet-stream")
    extension = ".mp4" if SERVICES[service_key].output_kind == "video" else ".png"
    return StreamingResponse(app.gpu_api.stream(upstream), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{service_key}_{job_id}{extension}"'
    })


@router.delete("/api/services/{service_key}/jobs/{job_id}")
def cancel(service_key: str, job_id: int, request: Request):
    app = core()
    user = app.current_user(request)
    con = app.db()
    row = con.execute("SELECT * FROM jobs WHERE id=? AND user_id=? AND service=?", (job_id, user["id"], service_key)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Không tìm thấy job")
    if row["status"] != "waiting":
        raise HTTPException(409, "Chỉ có thể hủy job đang chờ")
    try:
        app.service_adapters[service_key].cancel(row["worker_job_id"])
    except WorkerAdapterError as error:
        raise worker_error(error)
    return public_job(refresh_job(user["id"], job_id))


@router.get("/api/health/workers")
def health_workers(request: Request):
    app = core()
    app.require_admin(request)
    result = {key: {"title": SERVICES[key].title, **adapter.health()} for key, adapter in app.service_adapters.items()}
    result["video_upscale"] = {
        "title": "Nâng cấp video HD",
        **app.video_upscale_adapter.health(),
        "enabled": app.video_upscale_adapter.video_config.enabled,
    }
