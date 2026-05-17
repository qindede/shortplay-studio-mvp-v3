from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException

from ..ai import image as ai_image
from ..ai import llm as ai_llm
from ..ai import video as ai_video
from ..ai import voice as ai_voice
from ..ai.errors import AIError
from ..config import BACKEND_PUBLIC_URL, POINT_RULES
from .. import storage
from ..schemas import AssetGenerate, ComposeRequest, OutlineGenerateRequest, StoryboardGenerateRequest, VoiceCloneRequest
from ..storage_adapter import Storage
from ..utils import comparable_asset_names, now, uid

T = TypeVar("T")


def _run_paid_generation(
    user: dict,
    cost: int,
    scene: str,
    description: str,
    job_type: str,
    provider: str,
    work: Callable[[dict], tuple[T, dict[str, Any] | None]],
    failure_message: str = "生成失败",
    complete: bool = True,
    **links,
) -> T:
    job = Storage.start_paid_ai_job(user, cost, scene, description, job_type, provider, **links)
    try:
        result, output = work(job)
    except AIError as exc:
        Storage.fail_ai_job_with_refund(job["id"], exc.public_message)
        raise
    except storage.StorageError as exc:
        Storage.fail_ai_job_with_refund(job["id"], str(exc))
        raise
    except Exception as exc:
        Storage.fail_ai_job_with_refund(job["id"], str(exc) or failure_message)
        raise
    if complete:
        Storage.complete_ai_job(job["id"], output or {})
    return result


def generate_project_outline(user: dict, payload: OutlineGenerateRequest) -> dict:
    cost = POINT_RULES["outline"]
    def work(job: dict) -> tuple[dict, dict]:
        episodes = ai_llm.generate_outline(payload)
        return {"cost": cost, "episodes": episodes}, {"episode_count": len(episodes)}

    return _run_paid_generation(
        user,
        cost,
        "生成短剧大纲",
        f"智能生成《{payload.name}》短剧大纲",
        "outline",
        "minimax",
        work,
    )


def _generated_asset_payload(project_id: str, payload: dict, generated_url: str | None) -> dict:
    ts = now()
    refs = [{
        "id": uid("ref"),
        "type": "image",
        "name": f"AI 生成 - {payload['name']}",
        "url": generated_url,
        "note": payload["prompt"],
    }]
    return {
        "id": uid("asset"),
        "project_id": project_id,
        "type": payload["type"],
        "name": payload["name"],
        "description": payload.get("description", ""),
        "ref_count": len(refs),
        "initial": payload["name"][:1],
        "image": generated_url,
        "voice": None,
        "voice_url": None,
        "references": refs,
        "updated_at": ts,
    }


def generate_storyboard(user: dict, episode_id: str, payload: StoryboardGenerateRequest | None = None) -> list[dict]:
    context = Storage.episode_generation_context(user, episode_id)
    if not context:
        raise HTTPException(status_code=404, detail="episode not found")

    existing_assets = context["assets"]
    confirmed_assets = [item.model_dump() for item in (payload.confirmed_assets if payload else [])]
    existing_names = {
        item
        for asset in existing_assets
        for item in comparable_asset_names(asset)
        if asset.get("type") in {"character", "scene"}
    }
    assets_to_generate = [item for item in confirmed_assets if item["name"].strip() not in existing_names]
    total_cost = POINT_RULES["storyboard"] + len(assets_to_generate) * POINT_RULES["image_asset"]

    def work(job: dict) -> tuple[list[dict], dict]:
        generated_assets = []
        for item in assets_to_generate:
            generated_url = ai_image.generate_image(item["prompt"])
            generated_assets.append(_generated_asset_payload(context["project"]["id"], item, generated_url))
        ai_shots = ai_llm.generate_storyboard(context["project"], context["episode"], existing_assets + generated_assets)
        shots = Storage.save_storyboard_without_charge(user, episode_id, ai_shots, generated_assets)
        return shots, {"shot_count": len(shots), "generated_asset_count": len(generated_assets)}

    return _run_paid_generation(
        user,
        total_cost,
        "生成分镜",
        f"生成/更新《{context['episode']['title']}》分镜，含 {len(assets_to_generate)} 个素材",
        "storyboard",
        "minimax",
        work,
        project_id=context["project"]["id"],
        episode_id=episode_id,
    )


def _video_cost(shot: dict) -> int:
    return max(1, int(shot.get("duration") or 1)) * POINT_RULES["video_second"]


def _reference_image(assets: list[dict], shot: dict) -> str | None:
    character_names = {name.strip() for name in shot.get("characters", []) if name.strip()}
    scene = (shot.get("scene") or "").strip()
    candidates = []
    if character_names:
        candidates.extend(asset for asset in assets if asset.get("type") == "character" and asset.get("name") in character_names)
    if scene:
        candidates.extend(asset for asset in assets if asset.get("type") == "scene" and asset.get("name") == scene)
    candidates.extend(asset for asset in assets if asset.get("type") in {"image", "scene", "character"})
    for asset in candidates:
        media_url = _provider_media_url(asset.get("image"))
        if media_url:
            return media_url
    return None


def _provider_media_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/uploads/") and BACKEND_PUBLIC_URL:
        return f"{BACKEND_PUBLIC_URL.rstrip('/')}{url}"
    return None


def generate_video_for_shot(user: dict, shot_id: str) -> dict:
    shot, episode, assets = Storage.get_shot_with_context(user, shot_id)
    cost = _video_cost(shot)

    def work(job: dict) -> tuple[dict, dict]:
        provider_task_id = ai_video.create_video_task(
            shot.get("visual") or shot["title"],
            _reference_image(assets, shot),
            shot["duration"],
        )
        task = Storage.attach_video_task_to_job(user, shot_id, provider_task_id, job["id"])
        return task, {}

    return _run_paid_generation(
        user,
        cost,
        "生成镜头视频",
        f"生成镜头 #{shot['no']}《{shot['title']}》，{max(1, int(shot.get('duration') or 1))}s",
        "video_shot",
        "seedance",
        work,
        complete=False,
        project_id=episode.get("project_id") if episode else None,
        episode_id=shot.get("episode_id"),
        shot_id=shot.get("id"),
    )


def generate_videos_for_episode(user: dict, episode_id: str) -> list[dict]:
    context = Storage.episode_generation_context(user, episode_id)
    if not context:
        raise HTTPException(status_code=404, detail="episode not found")
    shots = context.get("shots", [])
    if not shots:
        raise HTTPException(status_code=404, detail="shots not found")
    tasks = []
    for shot in shots:
        tasks.append(generate_video_for_shot(user, shot["id"]))
    return tasks


def generate_asset(user: dict, project_id: str, payload: AssetGenerate) -> dict:
    visual_asset = payload.type in {"character", "scene", "image"}
    Storage.get_project(user, project_id)
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
        asset = Storage.generate_asset_without_charge(user, project_id, payload, generated_url, refs)
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


def start_voice_clone(user: dict, asset_id: str, payload: VoiceCloneRequest) -> dict:
    if not payload.consent:
        raise HTTPException(status_code=400, detail="请确认已获得声音授权")
    asset = Storage.get_asset(user, asset_id)
    voice_url = payload.voice_url or asset.get("voice_url")
    if not voice_url or not voice_url.startswith("/uploads/"):
        raise HTTPException(status_code=400, detail="请先上传角色声音样本")

    def work(job: dict) -> tuple[dict, dict]:
        audio, _ = storage.get_object(voice_url.removeprefix("/uploads/"))
        speaker_id = asset.get("speaker_id") or f"S_{asset_id.replace('-', '_')}_{uid('voice')[-10:]}"
        result = ai_voice.clone_voice(speaker_id, audio, voice_url.rsplit(".", 1)[-1] if "." in voice_url else "wav")
        updated = Storage.update_voice_clone_with_job(user, asset_id, result, job["id"])
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


def compose_episode(user: dict, episode_id: str, payload: ComposeRequest, compose_video_file) -> dict:
    context = Storage.compose_context(user, episode_id)
    if not context:
        raise HTTPException(status_code=404, detail="episode not found")
    shots = context.get("shots", [])
    if not shots or any(shot.get("status") != "completed" for shot in shots):
        raise HTTPException(status_code=400, detail="所有镜头完成后才能合成本集视频")

    def work(job: dict) -> tuple[dict, dict | None]:
        shot_order = {shot["id"]: shot["no"] for shot in shots}
        video_url = compose_video_file(sorted(context.get("video_tasks", []), key=lambda item: shot_order.get(item.get("shot_id"), 0)))
        version = Storage.save_composed_version_with_job(user, episode_id, payload, video_url, job["id"])
        return version, None

    return _run_paid_generation(
        user,
        POINT_RULES["compose"],
        "合成成片",
        f"合成《{context['episode']['title']}》成片版本",
        "compose",
        "ffmpeg",
        work,
        complete=False,
        failure_message="合成失败",
        project_id=context["project"]["id"],
        episode_id=episode_id,
    )
