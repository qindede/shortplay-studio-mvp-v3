"""Storyboard feature — business logic (service layer)."""
from __future__ import annotations

from ...ai import image as ai_image
from ...ai import llm as ai_llm
from ...config import POINT_RULES
from ...schemas import OutlineGenerateRequest, StoryboardGenerateRequest
from ...utils import comparable_asset_names, now, uid
from ..ai_job.service import run_paid_generation as _run_paid_generation
from ..errors import DomainError
from . import queries


def generate_project_outline(user: dict, payload: OutlineGenerateRequest) -> dict:
    """Generate a project outline via AI, charging points through the paid generation flow."""
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
    """Pure data builder: construct an asset dict from generation payload."""
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
    """Generate storyboard shots and any missing assets via AI, persisting through save_storyboard."""
    context = queries.episode_generation_context(user, episode_id)
    if not context:
        raise DomainError(404, "剧集不存在")

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
        shots = queries.save_storyboard(
            user,
            episode_id,
            ai_shots,
            generated_assets,
            POINT_RULES["storyboard"],
            POINT_RULES["image_asset"],
            now(),
            charge=False,
        )
        if shots is None:
            raise DomainError(404, "剧集不存在")
        if isinstance(shots, dict) and shots.get("error"):
            raise DomainError(402, "积分不足")
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


def storyboard_missing_assets(ai_shots: list[dict], assets: list[dict]) -> list[dict]:
    """Pure logic: scan AI-generated shots for character/scene names not yet in the asset list."""
    existing = {
        "character": set().union(*(comparable_asset_names(asset) for asset in assets if asset.get("type") == "character")),
        "scene": set().union(*(comparable_asset_names(asset) for asset in assets if asset.get("type") == "scene")),
    }
    missing: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add_candidate(asset_type: str, name: str, description: str) -> None:
        clean_name = name.strip()
        if not clean_name or clean_name in existing[asset_type]:
            return
        key = (asset_type, clean_name)
        if key in seen:
            return
        seen.add(key)
        label = "角色" if asset_type == "character" else "场景"
        missing.append({
            "type": asset_type,
            "name": clean_name,
            "description": description or f"本集分镜中出现的新{label}",
            "prompt": f"{clean_name}，{description or f'短剧本集需要使用的新{label}'}",
        })

    for shot in ai_shots:
        visual = shot.get("visual", "")
        dialogue = shot.get("dialogue", "")
        context = "；".join(part for part in [visual, dialogue] if part)
        for character in shot.get("characters") or []:
            add_candidate("character", str(character), context)
        add_candidate("scene", str(shot.get("scene") or ""), visual)

    return missing


def prepare_storyboard(user: dict, episode_id: str) -> dict:
    """Preview endpoint: generate storyboard without persisting, return cost + missing assets."""
    from ...ai.errors import AIError
    from ..points.service import ensure_points

    context = queries.episode_generation_context(user, episode_id)
    if not context:
        raise DomainError(404, "剧集不存在")
    ensure_points(user, POINT_RULES["storyboard"])
    try:
        ai_shots = ai_llm.generate_storyboard(context["project"], context["episode"], context["assets"])
    except AIError as exc:
        raise DomainError(503, exc.public_message)
    return {
        "cost": POINT_RULES["storyboard"],
        "asset_cost": POINT_RULES["image_asset"],
        "missing_assets": storyboard_missing_assets(ai_shots, context["assets"]),
    }


def optimize_prompt(prompt: str, context: str, project_name: str) -> dict:
    """Optimize a user prompt via AI."""
    from ...ai.errors import AIError

    try:
        return {"optimized": ai_llm.optimize_prompt(prompt, context, project_name)}
    except AIError as exc:
        raise DomainError(503, exc.public_message)
