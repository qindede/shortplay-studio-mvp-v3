"""Episode database access. No HTTP exceptions here."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text

from ...config import STATUS_LABEL
from ...db import SessionLocal, require_db
from ...models import Episode, Project, Shot, VideoVersion
from ...serializers import _episode_dict
from ...utils import fmt_dt, parse_dt, uid


@require_db
def list_episodes(user: dict[str, Any], project_id: str) -> list[dict[str, Any]] | None:

    with SessionLocal() as db:
        owned = db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not owned:
            return None
        rows = db.execute(
            text(
                """
                SELECT
                    e.id,
                    e.project_id,
                    e.no,
                    e.title,
                    COALESCE(e.summary, '') AS summary,
                    COALESCE(e.script, '') AS script,
                    e.duration_target,
                    e.status,
                    e.updated_at,
                    (SELECT count(*) FROM shots s WHERE s.episode_id = e.id) AS shot_count,
                    (SELECT count(*) FROM video_versions v WHERE v.episode_id = e.id) AS version_count
                FROM episodes e
                WHERE e.project_id = :project_id
                ORDER BY e.no
                """
            ),
            {"project_id": project_id},
        ).mappings()
        return [
            {
                "id": row["id"],
                "project_id": row["project_id"],
                "no": row["no"],
                "title": row["title"],
                "summary": row["summary"],
                "script": row["script"],
                "duration_target": row["duration_target"],
                "status": row["status"],
                "status_label": STATUS_LABEL.get(row["status"], row["status"]),
                "updated_at": fmt_dt(row["updated_at"]),
                "shot_count": int(row["shot_count"] or 0),
                "version_count": int(row["version_count"] or 0),
            }
            for row in rows
        ]


@require_db
def get_episode(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        shot_count = db.scalar(select(func.count(Shot.id)).where(Shot.episode_id == episode.id))
        version_count = db.scalar(select(func.count(VideoVersion.id)).where(VideoVersion.episode_id == episode.id))
        return _episode_dict(episode, shot_count, version_count)


@require_db
def create_episode(user: dict[str, Any], project_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not project:
            return None
        next_no = (db.scalar(select(func.max(Episode.no)).where(Episode.project_id == project_id)) or 0) + 1
        episode = Episode(
            id=uid("ep"),
            project_id=project_id,
            no=next_no,
            title=payload.title,
            summary=payload.summary,
            script=payload.script or payload.summary,
            duration_target=payload.duration_target,
            status="draft",
            updated_at=ts,
        )
        project.updated_at = ts
        db.add(episode)
        db.commit()
        return _episode_dict(episode)


@require_db
def update_episode(user: dict[str, Any], episode_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        updates = payload.model_dump(exclude_none=True)
        for field in ("title", "summary", "script", "duration_target", "status"):
            if field in updates:
                setattr(episode, field, updates[field])
        episode.updated_at = ts
        project = db.get(Project, episode.project_id)
        if project:
            project.updated_at = ts
        db.commit()
        return get_episode(user, episode_id)


@require_db
def delete_episode(user: dict[str, Any], episode_id: str, timestamp: str) -> tuple[bool, str | None]:
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return False, None
        project_id = episode.project_id
        removed_no = episode.no
        db.delete(episode)
        for item in db.scalars(select(Episode).where(Episode.project_id == project_id, Episode.no > removed_no)):
            item.no -= 1
        project = db.get(Project, project_id)
        if project:
            project.updated_at = parse_dt(timestamp)
        db.commit()
        return True, project_id
