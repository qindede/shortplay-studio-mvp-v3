from __future__ import annotations

from typing import Any

from ...ai import image as ai_image
from ...ai import voice as ai_voice
from ...ai.errors import AIError
from ...config import POINT_RULES
from ... import storage
from ...utils import normalize_refs, now, uid
from ..ai_job.service import run_paid_generation as _run_paid_generation
from ..errors import BadRequestError, InsufficientPointsError, NotFoundError
from . import db


def list_assets(user: dict[str, Any], project_id: str, asset_type: str | None = None) -> list[dict]:
    result = db.list_assets(user, project_id, asset_type)
    if result is None:
        raise NotFoundError("项目不存在")
    return result


def get_asset(user: dict[str, Any], asset_id: str) -> dict:
    result = db.get_asset(user, asset_id)
    if result is None:
        raise NotFoundError("素材不存在")
    return result


def create_asset(user: dict[str, Any], project_id: str, payload: Any) -> dict:
    refs = normalize_refs(payload.references)
    visual_asset = payload.type in {"character", "scene", "image"}
    cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
    result = db.create_asset(user, project_id, payload, refs, cost, now())
    if result is None:
        raise NotFoundError("项目不存在")
    if isinstance(result, dict) and result.get("error") == "insufficient_points":
        raise InsufficientPointsError(f"积分不足：本次需要 {cost}")
    return result


def generate_asset(user: dict[str, Any], project_id: str, payload: Any) -> dict:
    """Generate an asset using AI image generation."""
    from ..project.service import get_project
    project = get_project(user, project_id)

    visual_asset = payload.type in {"character", "scene", "image"}
    cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
    provider = "seedream" if visual_asset else "manual"

    def work(job: dict) -> tuple[dict, dict]:
        generated_url = ai_image.generate_image(payload.prompt) if visual_asset else None
        refs = [{
            "id": uid("ref"),
            "type": "image" if visual_asset else "audio",
            "name": f"AI 生成 - {payload.name}",
            "url": generated_url,
            "note": payload.prompt,
        }]
        asset = db.generate_asset_without_charge(user, project_id, payload, generated_url, refs, now())
        return asset, {"asset_id": asset["id"], "url": generated_url}

    return _run_paid_generation(
        user,
        cost,
        "AI 生成素材",
        f"AI 生成素材《{payload.name}》",
        "image_asset" if visual_asset else "audio_asset",
        provider,
        work,
        project_id=project_id,
    )


def start_voice_clone(user: dict[str, Any], asset_id: str, payload: Any) -> dict:
    """Start voice cloning for an asset."""
    if not payload.consent:
        raise BadRequestError("请确认已获得声音授权")
    asset = get_asset(user, asset_id)
    voice_url = payload.voice_url or asset.get("voice_url")
    if not voice_url or not voice_url.startswith("/uploads/"):
        raise BadRequestError("请先上传角色声音样本")

    def work(job: dict) -> tuple[dict, dict]:
        audio, _ = storage.get_object(voice_url.removeprefix("/uploads/"))
        speaker_id = asset.get("speaker_id") or f"S_{asset_id.replace('-', '_')}_{uid('voice')[-10:]}"
        result = ai_voice.clone_voice(speaker_id, audio, voice_url.rsplit(".", 1)[-1] if "." in voice_url else "wav")
        updated = db.update_voice_clone(user, asset_id, result, 0, now(), consume=False, job_id=job["id"])
        return updated, {}

    return _run_paid_generation(
        user,
        POINT_RULES["voice_clone"],
        "音色克隆",
        f"训练《{asset['name']}》角色音色",
        "voice_clone",
        "volc_voice",
        work,
        complete=False,
        project_id=asset.get("project_id"),
        asset_id=asset_id,
    )


def update_asset(user: dict[str, Any], asset_id: str, payload: Any) -> dict:
    refs_raw = payload.model_dump(exclude_unset=True).get("references")
    refs = normalize_refs(refs_raw) if refs_raw is not None else None
    result = db.update_asset(user, asset_id, payload, refs, now())
    if result is None:
        raise NotFoundError("素材不存在")
    return result


def delete_asset(user: dict[str, Any], asset_id: str) -> dict:
    if not db.delete_asset(user, asset_id):
        raise NotFoundError("素材不存在")
    return {"ok": True}


def update_voice_clone(user: dict[str, Any], asset_id: str, result: dict[str, Any], cost: int = 0, consume: bool = True, job_id: str | None = None) -> dict:
    updated = db.update_voice_clone(user, asset_id, result, cost, now(), consume=consume, job_id=job_id)
    if updated is None:
        raise NotFoundError("素材不存在")
    if isinstance(updated, dict) and updated.get("error") == "insufficient_points":
        raise InsufficientPointsError("积分不足")
    return updated


def get_voice_clone(user: dict[str, Any], asset_id: str) -> dict:
    """Fetch latest voice clone status from provider and update local record."""
    asset = get_asset(user, asset_id)
    if not asset.get("speaker_id"):
        return asset
    try:
        result = ai_voice.get_voice(asset["speaker_id"])
    except AIError:
        return asset
    return update_voice_clone(user, asset_id, result, cost=0, consume=False)
