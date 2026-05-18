"""Shot database access. No HTTP exceptions here."""
from __future__ import annotations

from collections import defaultdict
import json
from typing import Any

from sqlalchemy import select, text

from ...db import SessionLocal, require_db
from ...models import Asset, AssetReference, Episode, Project, Shot
from ...serializers import _asset_dict, _episode_dict, _project_dict, _shot_dict
from ...utils import parse_dt


@require_db
def shot_generation_context(user: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        shot = db.scalar(
            select(Shot)
            .join(Episode, Episode.id == Shot.episode_id)
            .join(Project, Project.id == Episode.project_id)
            .where(Shot.id == shot_id, Project.owner_user_id == user["id"])
        )
        if not shot:
            return None
        episode = db.get(Episode, shot.episode_id)
        project = db.get(Project, episode.project_id) if episode else None
        if episode:
            asset_rows = list(db.scalars(select(Asset).where(Asset.project_id == episode.project_id)))
            refs_by_asset: dict[str, list[dict]] = defaultdict(list)
            asset_ids = [a.id for a in asset_rows]
            if asset_ids:
                for ref in db.scalars(select(AssetReference).where(AssetReference.asset_id.in_(asset_ids)).order_by(AssetReference.sort_order)):
                    refs_by_asset[ref.asset_id].append({"id": ref.id, "type": ref.type, "name": ref.name, "url": ref.url, "note": ref.note})
            assets = [_asset_dict(a, refs_by_asset.get(a.id, [])) for a in asset_rows]
        else:
            assets = []
        return {
            "shot": _shot_dict(shot),
            "episode": _episode_dict(episode) if episode else None,
            "project": _project_dict(project) if project else None,
            "assets": assets or [],
        }


@require_db
def create_shot(user: dict[str, Any], episode_id: str, payload: Any, shot_id: str, updated_at: str) -> dict[str, Any] | None:

    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                WITH target_episode AS (
                    SELECT e.id, e.project_id
                    FROM episodes e
                    JOIN projects p ON p.id = e.project_id
                    WHERE e.id = :episode_id
                      AND p.owner_user_id = :user_id
                    LIMIT 1
                ),
                next_no AS (
                    SELECT COALESCE(MAX(s.no), 0) + 1 AS no
                    FROM shots s
                    WHERE s.episode_id = :episode_id
                ),
                inserted AS (
                    INSERT INTO shots (
                        id,
                        episode_id,
                        no,
                        title,
                        visual,
                        dialogue,
                        characters,
                        scene,
                        duration,
                        status,
                        updated_at
                    )
                    SELECT
                        :shot_id,
                        target_episode.id,
                        next_no.no,
                        :title,
                        :visual,
                        :dialogue,
                        CAST(:characters AS jsonb),
                        :scene,
                        :duration,
                        'pending',
                        :updated_at
                    FROM target_episode, next_no
                    RETURNING id, episode_id, no, title, visual, dialogue, characters, scene, duration, status, updated_at
                ),
                touched_episode AS (
                    UPDATE episodes e
                    SET status = 'storyboard_ready',
                        updated_at = :updated_at
                    FROM target_episode te
                    WHERE e.id = te.id
                    RETURNING e.project_id
                )
                UPDATE projects p
                SET updated_at = :updated_at
                FROM touched_episode te
                WHERE p.id = te.project_id
                RETURNING (
                    SELECT jsonb_build_object(
                        'id', i.id,
                        'episode_id', i.episode_id,
                        'no', i.no,
                        'title', i.title,
                        'visual', COALESCE(i.visual, ''),
                        'dialogue', COALESCE(i.dialogue, ''),
                        'characters', i.characters,
                        'scene', COALESCE(i.scene, ''),
                        'duration', i.duration,
                        'status', i.status,
                        'updated_at', i.updated_at
                    )
                    FROM inserted i
                ) AS shot
                """
            ),
            {
                "user_id": user["id"],
                "episode_id": episode_id,
                "shot_id": shot_id,
                "title": payload.title,
                "visual": payload.visual,
                "dialogue": payload.dialogue,
                "characters": json.dumps(payload.characters, ensure_ascii=False),
                "scene": payload.scene,
                "duration": payload.duration,
                "updated_at": parse_dt(updated_at),
            },
        ).mappings().first()
        db.commit()
        if not row or not row["shot"]:
            return None
        return dict(row["shot"])


@require_db
def list_shots(user: dict[str, Any], episode_id: str) -> list[dict[str, Any]] | None:

    with SessionLocal() as db:
        owned = db.scalar(
            select(Episode.id)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not owned:
            return None
        rows = db.scalars(select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.no))
        return [_shot_dict(row) for row in rows]


@require_db
def patch_shot(user: dict[str, Any], shot_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        shot = db.scalar(
            select(Shot)
            .join(Episode, Episode.id == Shot.episode_id)
            .join(Project, Project.id == Episode.project_id)
            .where(Shot.id == shot_id, Project.owner_user_id == user["id"])
        )
        if not shot:
            return None
        updates = payload.model_dump(exclude_none=True)
        for field in ("title", "visual", "dialogue", "characters", "scene", "duration"):
            if field in updates:
                setattr(shot, field, updates[field])
        shot.updated_at = ts
        episode = db.get(Episode, shot.episode_id)
        if episode:
            episode.updated_at = ts
            project = db.get(Project, episode.project_id)
            if project:
                project.updated_at = ts
        db.commit()
        return _shot_dict(shot)


@require_db
def delete_shot(user: dict[str, Any], shot_id: str, timestamp: str) -> bool:
    with SessionLocal() as db:
        shot = db.scalar(
            select(Shot)
            .join(Episode, Episode.id == Shot.episode_id)
            .join(Project, Project.id == Episode.project_id)
            .where(Shot.id == shot_id, Project.owner_user_id == user["id"])
        )
        if not shot:
            return False
        episode_id = shot.episode_id
        removed_no = shot.no
        db.delete(shot)
        for item in db.scalars(select(Shot).where(Shot.episode_id == episode_id, Shot.no > removed_no)):
            item.no -= 1
        episode = db.get(Episode, episode_id)
        if episode:
            episode.updated_at = parse_dt(timestamp)
            project = db.get(Project, episode.project_id)
            if project:
                project.updated_at = episode.updated_at
        db.commit()
        return True
