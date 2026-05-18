"""Project database access. No HTTP exceptions here."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text

from ...config import STATUS_LABEL
from ...db import SessionLocal, require_db
from ...models import Asset, Episode, Project, VideoVersion
from ...serializers import _project_dict
from ...utils import fmt_dt, parse_dt, uid


@require_db
def list_projects(user: dict[str, Any]) -> list[dict[str, Any]]:

    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                    p.id,
                    p.owner_user_id,
                    p.name,
                    p.short_name,
                    COALESCE(p.description, '') AS description,
                    p.status,
                    p.cover,
                    p.cover_image_url AS cover_image,
                    p.created_at,
                    p.updated_at,
                    (SELECT count(*) FROM episodes e WHERE e.project_id = p.id) AS episode_count,
                    (SELECT count(*) FROM assets a WHERE a.project_id = p.id) AS asset_count,
                    (SELECT count(*) FROM video_versions v WHERE v.project_id = p.id) AS version_count
                FROM projects p
                WHERE p.owner_user_id = :user_id
                ORDER BY p.updated_at DESC
                """
            ),
            {"user_id": user["id"]},
        ).mappings()
        return [
            {
                "id": row["id"],
                "owner_user_id": row["owner_user_id"],
                "owner": user.get("display_name", ""),
                "name": row["name"],
                "short_name": row["short_name"],
                "description": row["description"],
                "status": row["status"],
                "status_label": STATUS_LABEL.get(row["status"], row["status"]),
                "cover": row["cover"],
                "cover_image": row["cover_image"],
                "created_at": fmt_dt(row["created_at"]),
                "updated_at": fmt_dt(row["updated_at"]),
                "episode_count": int(row["episode_count"] or 0),
                "asset_count": int(row["asset_count"] or 0),
                "version_count": int(row["version_count"] or 0),
            }
            for row in rows
        ]


@require_db
def get_project(user: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        project = db.scalar(
            select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"])
        )
        if not project:
            return None
        episode_count = db.scalar(select(func.count(Episode.id)).where(Episode.project_id == project_id)) or 0
        asset_count = db.scalar(select(func.count(Asset.id)).where(Asset.project_id == project_id)) or 0
        version_count = db.scalar(select(func.count(VideoVersion.id)).where(VideoVersion.project_id == project_id)) or 0
        return _project_dict(project, episode_count, asset_count, version_count)


@require_db
def create_project(user: dict[str, Any], payload: Any, timestamp: str) -> dict[str, Any]:
    ts = parse_dt(timestamp)
    project = Project(
        id=uid("proj"),
        owner_user_id=user["id"],
        name=payload.name.strip(),
        short_name=payload.name.strip()[:8],
        description=payload.description,
        status="draft",
        cover="dark",
        created_at=ts,
        updated_at=ts,
    )
    with SessionLocal() as db:
        db.add(project)
        db.flush()
        for index, item in enumerate(payload.episodes, start=1):
            db.add(
                Episode(
                    id=uid("ep"),
                    project_id=project.id,
                    no=index,
                    title=item.title,
                    summary=item.summary,
                    script=item.script or item.summary,
                    duration_target=item.duration_target,
                    status="draft",
                    updated_at=ts,
                )
            )
        db.commit()
        return _project_dict(project, len(payload.episodes), 0, 0) | {"owner": user.get("display_name", "")}


@require_db
def update_project(user: dict[str, Any], project_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not project:
            return None
        updates = payload.model_dump(exclude_none=True)
        if "name" in updates:
            project.name = updates["name"].strip()
            project.short_name = project.name[:8]
        if "description" in updates:
            project.description = updates["description"]
        if "status" in updates:
            project.status = updates["status"]
        project.updated_at = parse_dt(timestamp)
        db.commit()
        return get_project(user, project_id)


@require_db
def delete_project(user: dict[str, Any], project_id: str) -> bool:
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not project:
            return False
        db.delete(project)
        db.commit()
        return True
