from __future__ import annotations

from .. import storage
from ..config import AI
from .client import get_json, post_json, require_key
from .errors import AIOutputSchemaError


def create_video_task(prompt: str, image_url: str | None, duration: int) -> str:
    key = require_key(AI.ark_api_key, "ARK_API_KEY")
    text = f"{prompt} --resolution 1080p --ratio 9:16 --duration {max(1, duration)} --watermark true"
    content: list[dict] = [{"type": "text", "text": text}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    body = post_json(
        f"{AI.ark_base_url.rstrip('/')}/contents/generations/tasks",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {"model": AI.ark_video_model, "content": content},
        AI.request_timeout,
    )
    task_id = body.get("id") or body.get("task_id") or body.get("data", {}).get("id")
    if not task_id:
        raise AIOutputSchemaError("Video provider did not return a task id")
    return task_id


def query_video_task(task_id: str) -> dict:
    key = require_key(AI.ark_api_key, "ARK_API_KEY")
    body = get_json(
        f"{AI.ark_base_url.rstrip('/')}/contents/generations/tasks/{task_id}",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        AI.request_timeout,
    )
    status = str(body.get("status") or body.get("data", {}).get("status") or "").lower()
    progress = int(body.get("progress") or body.get("data", {}).get("progress") or 0)
    result_url = (
        body.get("content", {}).get("video_url")
        or body.get("video_url")
        or body.get("data", {}).get("video_url")
        or body.get("data", {}).get("url")
    )
    mapped = "generating"
    if status in {"succeeded", "success", "completed"}:
        mapped = "completed"
        progress = 100
    elif status in {"failed", "error", "cancelled"}:
        mapped = "failed"
    video_url = storage.upload_from_url(result_url, "videos", ".mp4") if result_url and mapped == "completed" else None
    return {
        "status": mapped,
        "progress": progress,
        "video_url": video_url,
        "error": body.get("error") or body.get("message"),
    }
