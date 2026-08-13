"""Best-effort HD post-processing for completed video jobs."""
from __future__ import annotations

from service_worker_adapters import WorkerAdapterError, normalize_status


def start(app, row: dict) -> dict:
    config = app.video_upscale_adapter.video_config
    if not config.configured or row.get("video_upscale_attempted"):
        return {"status": "done", "progress": 100}
    original = None
    try:
        if row.get("service") == "video_generation":
            original = app.service_adapters[row["service"]].result(row["worker_job_id"])
        elif row.get("output_path"):
            path = app.BASE / row["output_path"]
            original = path.open("rb")
        elif row.get("gpu_job_id"):
            original = app.gpu_api.output(str(row["user_id"]), row["gpu_job_id"])
        else:
            return {"status": "done", "progress": 100}
        source = original.raw if hasattr(original, "raw") else original
        media_type = getattr(original, "headers", {}).get("content-type", "video/mp4")
        accepted = app.video_upscale_adapter.submit(
            f"tvc-{row['id']}-hd",
            {
                "target_short_side": config.target_short_side,
                "preserve_aspect_ratio": True,
                "preserve_fps": True,
                "preserve_duration": True,
                "preserve_audio": True,
                "identity_and_motion_passthrough": True,
            },
            {"source_video": ("original.mp4", source, media_type)},
        )
        return {
            "status": "upscaling", "progress": 90, "attempted": 1,
            "upscale_job_id": accepted["job_id"], "upscale_status": accepted["status"],
        }
    except (WorkerAdapterError, OSError, AttributeError, TypeError) as error:
        return {
            "status": "done", "progress": 100, "attempted": 1,
            "upscale_status": "failed", "upscale_error": str(error)[:1000],
        }
    finally:
        if original is not None:
            original.close()


def poll(app, row: dict) -> dict:
    try:
        payload = app.video_upscale_adapter.status(row["video_upscale_job_id"])
        status = normalize_status(payload.get("status"))
    except WorkerAdapterError as error:
        status, payload = "failed", {"error": error.message}
    if status in {"queued", "processing"}:
        try:
            worker_progress = int(payload.get("progress", 0) or 0)
        except (TypeError, ValueError):
            worker_progress = 0
        return {"status": "upscaling", "progress": max(90, min(99, worker_progress)), "upscale_status": status}
    if status == "completed":
        return {"status": "done", "progress": 100, "upscale_status": "completed"}
    return {
        "status": "done", "progress": 100, "upscale_status": "failed",
        "upscale_error": str(payload.get("error") or "Không thể nâng cấp HD")[:1000],
    }


def persist(app, job_id: int, values: dict) -> dict:
    con = app.db()
    con.execute(
        """UPDATE jobs SET status=?,progress=?,
           video_upscale_attempted=MAX(video_upscale_attempted,?),
           video_upscale_job_id=COALESCE(?,video_upscale_job_id),
           video_upscale_status=COALESCE(?,video_upscale_status),
           video_upscale_error=COALESCE(?,video_upscale_error),updated_at=?
           WHERE id=?""",
        (values["status"], values["progress"], values.get("attempted", 0),
         values.get("upscale_job_id"), values.get("upscale_status"),
         values.get("upscale_error"), app.now_iso(), job_id)
    )
    con.commit()
    row = dict(con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    con.close()
    return row


def result_response(app, row):
    if row["video_upscale_status"] == "completed" and row["video_upscale_job_id"]:
        try:
            return app.video_upscale_adapter.result(row["video_upscale_job_id"])
        except WorkerAdapterError:
            pass
    if row["service"] == "video_generation":
        return app.service_adapters[row["service"]].result(row["worker_job_id"])
    return None
