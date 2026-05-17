from __future__ import annotations

from fastapi import HTTPException

from ..ai import image as ai_image
from ..ai import llm as ai_llm
from ..ai.errors import AIError
from ..config import POINT_RULES
from ..schemas import OutlineGenerateRequest, StoryboardGenerateRequest
from ..storage_adapter import Storage
from ..utils import comparable_asset_names, now, uid


def generate_project_outline(user: dict, payload: OutlineGenerateRequest) -> dict:
    cost = POINT_RULES["outline"]
    job = Storage.start_paid_ai_job(
        user,
        cost,
        "生成短剧大纲",
        f"智能生成《{payload.name}》短剧大纲",
        "outline",
        "minimax",
    )
    try:
        episodes = ai_llm.generate_outline(payload)
    except AIError as exc:
        Storage.fail_ai_job_with_refund(job["id"], exc.public_message)
        raise
    except Exception as exc:
        Storage.fail_ai_job_with_refund(job["id"], str(exc) or "生成失败")
        raise
    Storage.complete_ai_job(job["id"], {"episode_count": len(episodes)})
    return {"cost": cost, "episodes": episodes}


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
    job = Storage.start_paid_ai_job(
        user,
        total_cost,
        "生成分镜",
        f"生成/更新《{context['episode']['title']}》分镜，含 {len(assets_to_generate)} 个素材",
        "storyboard",
        "minimax",
        project_id=context["project"]["id"],
        episode_id=episode_id,
    )

    try:
        generated_assets = []
        for item in assets_to_generate:
            generated_url = ai_image.generate_image(item["prompt"])
            generated_assets.append(_generated_asset_payload(context["project"]["id"], item, generated_url))
        ai_shots = ai_llm.generate_storyboard(context["project"], context["episode"], existing_assets + generated_assets)
        shots = Storage.save_storyboard_without_charge(user, episode_id, ai_shots, generated_assets)
    except AIError as exc:
        Storage.fail_ai_job_with_refund(job["id"], exc.public_message)
        raise
    except Exception as exc:
        Storage.fail_ai_job_with_refund(job["id"], str(exc) or "生成失败")
        raise

    Storage.complete_ai_job(
        job["id"],
        {"shot_count": len(shots), "generated_asset_count": len(generated_assets)},
    )
    return shots
