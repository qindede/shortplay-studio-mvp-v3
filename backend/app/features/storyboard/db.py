"""Storyboard database access. No HTTP exceptions here."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import delete, select

from ...db import SessionLocal, require_db
from ...models import Asset, AssetReference, Episode, Project, Shot, VideoTask
from ...serializers import _asset_dict, _episode_dict, _project_dict, _shot_dict
from ...utils import parse_dt, uid
from ..ai_job.db import add_ai_job
from ..points.db import change_points


@require_db
def episode_generation_context(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    """Load episode with ownership check, project, all project assets with references, and all shots."""
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        project = db.get(Project, episode.project_id)
        asset_rows = list(db.scalars(select(Asset).where(Asset.project_id == episode.project_id)))
        refs_by_asset: dict[str, list[dict]] = defaultdict(list)
        asset_ids = [a.id for a in asset_rows]
        if asset_ids:
            for ref in db.scalars(select(AssetReference).where(AssetReference.asset_id.in_(asset_ids)).order_by(AssetReference.sort_order)):
                refs_by_asset[ref.asset_id].append({"id": ref.id, "type": ref.type, "name": ref.name, "url": ref.url, "note": ref.note})
        assets = [_asset_dict(a, refs_by_asset.get(a.id, [])) for a in asset_rows]
        shots = [_shot_dict(shot) for shot in db.scalars(select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.no))]
        return {
            "project": _project_dict(project) | {"owner": user.get("display_name", "")},
            "episode": _episode_dict(episode),
            "assets": assets,
            "shots": shots,
        }


@require_db
def save_storyboard(
    user: dict[str, Any],
    episode_id: str,
    ai_shots: list[dict],
    generated_assets: list[dict],
    storyboard_cost: int,
    asset_cost: int,
    timestamp: str,
    charge: bool = True,
) -> list[dict[str, Any]] | dict[str, str] | None:
    """Heavy transactional function: deduplicate/insert generated assets, optionally charge
    points + AI jobs, delete old VideoTask/Shot rows, insert new shots, set episode status."""
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        project = db.get(Project, episode.project_id)
        try:
            for item in generated_assets:
                duplicate = db.scalar(
                    select(Asset.id).where(
                        Asset.project_id == episode.project_id,
                        Asset.type == item["type"],
                        Asset.name == item["name"],
                    )
                )
                if duplicate:
                    continue
                if charge:
                    change_points(db, user["id"], -asset_cost, "consume", "AI 生成素材", f"AI 生成素材《{item['name']}》", ts)
                asset = Asset(
                    id=item["id"],
                    project_id=episode.project_id,
                    type=item["type"],
                    name=item["name"],
                    description=item.get("description", ""),
                    initial=item.get("initial") or item["name"][:1],
                    image_url=item.get("image"),
                    voice_label=item.get("voice"),
                    voice_url=item.get("voice_url"),
                    provider_meta={},
                    updated_at=ts,
                )
                db.add(asset)
                db.flush()
                for index, ref in enumerate(item.get("references", []) or []):
                    db.add(AssetReference(id=ref.get("id") or uid("ref"), asset_id=asset.id, type=ref.get("type", "image"), name=ref.get("name", f"参考 {index + 1}"), url=ref.get("url"), note=ref.get("note"), sort_order=index))
                if charge:
                    add_ai_job(db, user["id"], "image_asset", "seedream", asset_cost, ts, project_id=episode.project_id, asset_id=asset.id)

            if charge:
                change_points(db, user["id"], -storyboard_cost, "consume", "生成分镜", f"生成/更新《{episode.title}》分镜", ts)
                add_ai_job(db, user["id"], "storyboard", "minimax", storyboard_cost, ts, episode_id=episode_id, project_id=episode.project_id)
        except ValueError as exc:
            db.rollback()
            return {"error": str(exc)}

        db.execute(delete(VideoTask).where(VideoTask.episode_id == episode_id))
        db.execute(delete(Shot).where(Shot.episode_id == episode_id))
        new_shots = []
        for index, item in enumerate(ai_shots, start=1):
            shot = Shot(
                id=uid("shot"),
                episode_id=episode_id,
                no=index,
                title=item["title"],
                visual=item.get("visual", ""),
                dialogue=item.get("dialogue", ""),
                characters=item.get("characters", []),
                scene=item.get("scene", ""),
                duration=item.get("duration", 3),
                status="pending",
                updated_at=ts,
            )
            db.add(shot)
            new_shots.append(_shot_dict(shot))
        episode.status = "storyboard_ready"
        episode.updated_at = ts
        if project:
            project.updated_at = ts
        db.commit()
        return new_shots
