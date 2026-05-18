"""Data import/export utilities for seed data and migration scripts."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from .config import DEFAULT_USAGE
from .db import SessionLocal
from .models import (
    AiJob,
    Asset,
    AssetReference,
    Episode,
    PointLedger,
    Project,
    Shot,
    User,
    VideoVersion,
)
from .utils import fmt_dt, parse_dt, uid


def _ensure_seed_data() -> None:
    """Create default users and load seed data if the database is empty."""
    with SessionLocal() as db:
        has_users = db.scalar(select(User.id).limit(1))
        if has_users:
            return
        from .security import hash_password
        from .seed_data import seed_data
        ts = datetime.now()
        for username, display_name, role, points in [
            ("admin", "管理员", "admin", 100000),
            ("demo", "演示用户", "user", 2000),
        ]:
            db.add(User(
                id=uid("user"), username=username, display_name=display_name,
                password_hash=hash_password("admin123" if role == "admin" else "demo123"),
                role=role, status="active", points=points, token=None,
                usage_json={}, created_at=ts, last_login_at=None,
            ))
        db.commit()
    from .data_io import save_data
    save_data(seed_data())


def load_data() -> dict[str, Any]:
    _ensure_seed_data()
    with SessionLocal() as db:
        users = list(db.scalars(select(User)))
        user_by_id = {user.id: user for user in users}

        projects = [
            {
                "id": row.id,
                "owner_user_id": row.owner_user_id,
                "owner": user_by_id.get(row.owner_user_id).display_name if user_by_id.get(row.owner_user_id) else "",
                "name": row.name,
                "short_name": row.short_name,
                "description": row.description or "",
                "status": row.status,
                "cover": row.cover,
                "cover_image": row.cover_image_url,
                "created_at": fmt_dt(row.created_at),
                "updated_at": fmt_dt(row.updated_at),
            }
            for row in db.scalars(select(Project))
        ]
        episodes = [
            {
                "id": row.id,
                "project_id": row.project_id,
                "no": row.no,
                "title": row.title,
                "summary": row.summary or "",
                "script": row.script or "",
                "duration_target": row.duration_target,
                "status": row.status,
                "updated_at": fmt_dt(row.updated_at),
            }
            for row in db.scalars(select(Episode))
        ]
        shots = [
            {
                "id": row.id,
                "episode_id": row.episode_id,
                "no": row.no,
                "title": row.title,
                "visual": row.visual or "",
                "dialogue": row.dialogue or "",
                "characters": row.characters or [],
                "scene": row.scene or "",
                "duration": row.duration,
                "status": row.status,
                "updated_at": fmt_dt(row.updated_at),
            }
            for row in db.scalars(select(Shot))
        ]

        refs_by_asset: dict[str, list[dict]] = defaultdict(list)
        for ref in db.scalars(select(AssetReference).order_by(AssetReference.sort_order)):
            refs_by_asset[ref.asset_id].append(
                {
                    "id": ref.id,
                    "type": ref.type,
                    "name": ref.name,
                    "url": ref.url,
                    "note": ref.note,
                }
            )
        assets = [
            {
                "id": row.id,
                "project_id": row.project_id,
                "type": row.type,
                "name": row.name,
                "description": row.description or "",
                "ref_count": len(refs_by_asset.get(row.id, [])),
                "initial": row.initial or row.name[:1],
                "image": row.image_url,
                "voice": row.voice_label,
                "voice_url": row.voice_url,
                "speaker_id": row.speaker_id,
                "voice_status": row.voice_status,
                "references": refs_by_asset.get(row.id, []),
                "updated_at": fmt_dt(row.updated_at),
            }
            for row in db.scalars(select(Asset))
        ]
        video_versions = [
            {
                "id": row.id,
                "project_id": row.project_id,
                "episode_id": row.episode_id,
                "name": row.name,
                "description": row.description or "",
                "duration": row.duration,
                "ratio": row.ratio,
                "status": row.status,
                "theme": row.theme,
                "preview_url": row.preview_url,
                "video_url": row.video_url,
                "created_at": fmt_dt(row.created_at),
            }
            for row in db.scalars(select(VideoVersion))
        ]
        point_ledger = []
        for row in db.scalars(select(PointLedger).order_by(PointLedger.created_at.desc())):
            ledger_user = user_by_id.get(row.user_id)
            point_ledger.append(
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "username": ledger_user.username if ledger_user else "",
                    "display_name": ledger_user.display_name if ledger_user else "",
                    "amount": row.amount,
                    "type": row.type,
                    "scene": row.scene,
                    "description": row.description or "",
                    "balance_after": row.balance_after,
                    "ai_job_id": row.ai_job_id,
                    "created_at": fmt_dt(row.created_at),
                }
            )
        ai_jobs = [
            {
                "id": row.id,
                "user_id": row.user_id,
                "project_id": row.project_id,
                "episode_id": row.episode_id,
                "shot_id": row.shot_id,
                "asset_id": row.asset_id,
                "type": row.type,
                "provider": row.provider,
                "provider_task_id": row.provider_task_id,
                "status": row.status,
                "progress": row.progress,
                "input_json": row.input_json or {},
                "output_json": row.output_json or {},
                "error": row.error,
                "cost_points": row.cost_points,
                "created_at": fmt_dt(row.created_at),
                "updated_at": fmt_dt(row.updated_at),
                "completed_at": fmt_dt(row.completed_at),
            }
            for row in db.scalars(select(AiJob).order_by(AiJob.created_at.desc()))
        ]
        user_rows = [
            {
                "id": row.id,
                "username": row.username,
                "display_name": row.display_name,
                "password_hash": row.password_hash,
                "role": row.role,
                "status": row.status,
                "points": row.points,
                "token": row.token or "",
                "usage": row.usage_json or {},
                "created_at": fmt_dt(row.created_at),
                "last_login": fmt_dt(row.last_login_at),
            }
            for row in users
        ]
        usage = {
            **DEFAULT_USAGE,
            "video_used_seconds": sum((user.usage_json or {}).get("video_used_seconds", 0) for user in users),
            "image_used": sum((user.usage_json or {}).get("image_used", 0) for user in users),
            "export_used": sum((user.usage_json or {}).get("export_used", 0) for user in users),
            "team_members": len([user for user in users if user.status == "active"]),
        }
        return {
            "projects": projects,
            "episodes": episodes,
            "shots": shots,
            "assets": assets,
            "video_versions": video_versions,
            "usage": usage,
            "users": user_rows,
            "point_ledger": point_ledger,
            "ai_jobs": ai_jobs,
        }


def save_data(data: dict[str, Any]) -> None:
    with SessionLocal() as db:
        for model in [PointLedger, VideoVersion, AiJob, AssetReference, Asset, Shot, Episode, Project]:
            db.execute(delete(model))
        db.flush()

        for item in data.get("users", []):
            db.merge(
                User(
                    id=item["id"],
                    username=item["username"],
                    password_hash=item["password_hash"],
                    display_name=item.get("display_name") or item["username"],
                    role=item.get("role", "user"),
                    status=item.get("status", "active"),
                    points=int(item.get("points", 0)),
                    token=item.get("token") or None,
                    usage_json=item.get("usage", {}),
                    created_at=parse_dt(item.get("created_at")),
                    last_login_at=parse_dt(item.get("last_login")),
                )
            )
        db.flush()
        for item in data.get("projects", []):
            db.add(
                Project(
                    id=item["id"],
                    owner_user_id=item.get("owner_user_id", "user_admin"),
                    name=item["name"],
                    short_name=item.get("short_name") or item["name"][:8],
                    description=item.get("description", ""),
                    status=item.get("status", "draft"),
                    cover=item.get("cover"),
                    cover_image_url=item.get("cover_image") or item.get("cover_image_url"),
                    created_at=parse_dt(item.get("created_at")),
                    updated_at=parse_dt(item.get("updated_at")),
                )
            )
        db.flush()
        for item in data.get("episodes", []):
            db.add(
                Episode(
                    id=item["id"],
                    project_id=item["project_id"],
                    no=int(item["no"]),
                    title=item["title"],
                    summary=item.get("summary", ""),
                    script=item.get("script", ""),
                    duration_target=int(item.get("duration_target", 30)),
                    status=item.get("status", "draft"),
                    updated_at=parse_dt(item.get("updated_at")),
                )
            )
        db.flush()
        for item in data.get("shots", []):
            db.add(
                Shot(
                    id=item["id"],
                    episode_id=item["episode_id"],
                    no=int(item["no"]),
                    title=item["title"],
                    visual=item.get("visual", ""),
                    dialogue=item.get("dialogue", ""),
                    characters=item.get("characters", []),
                    scene=item.get("scene", ""),
                    duration=int(item.get("duration", 3)),
                    status=item.get("status", "pending"),
                    updated_at=parse_dt(item.get("updated_at")),
                )
            )
        db.flush()
        for item in data.get("assets", []):
            db.add(
                Asset(
                    id=item["id"],
                    project_id=item["project_id"],
                    type=item["type"],
                    name=item["name"],
                    description=item.get("description", ""),
                    initial=item.get("initial") or item["name"][:1],
                    image_url=item.get("image") or item.get("image_url"),
                    voice_label=item.get("voice"),
                    voice_url=item.get("voice_url"),
                    speaker_id=item.get("speaker_id"),
                    voice_status=item.get("voice_status"),
                    generation_prompt=item.get("generation_prompt"),
                    provider_meta=item.get("provider_meta", {}),
                    updated_at=parse_dt(item.get("updated_at")),
                )
            )
            for index, ref in enumerate(item.get("references", []) or []):
                db.add(
                    AssetReference(
                        id=ref.get("id") or f"{item['id']}_ref_{index + 1}",
                        asset_id=item["id"],
                        type=ref.get("type", "image"),
                        name=ref.get("name", f"参考 {index + 1}"),
                        url=ref.get("url"),
                        note=ref.get("note"),
                        sort_order=index,
                    )
                )
        db.flush()
        for item in data.get("ai_jobs", []):
            db.add(
                AiJob(
                    id=item["id"],
                    user_id=item["user_id"],
                    project_id=item.get("project_id"),
                    episode_id=item.get("episode_id"),
                    shot_id=item.get("shot_id"),
                    asset_id=item.get("asset_id"),
                    type=item["type"],
                    provider=item["provider"],
                    provider_task_id=item.get("provider_task_id"),
                    status=item.get("status", "running"),
                    progress=int(item.get("progress", 0)),
                    input_json=item.get("input_json", {}),
                    output_json=item.get("output_json", {}),
                    error=item.get("error"),
                    cost_points=int(item.get("cost_points", 0)),
                    created_at=parse_dt(item.get("created_at")),
                    updated_at=parse_dt(item.get("updated_at")),
                    completed_at=parse_dt(item.get("completed_at")),
                )
            )
        db.flush()
        for item in data.get("video_versions", []):
            db.add(
                VideoVersion(
                    id=item["id"],
                    project_id=item["project_id"],
                    episode_id=item["episode_id"],
                    name=item["name"],
                    description=item.get("description", ""),
                    duration=int(item.get("duration", 1)),
                    ratio=item.get("ratio", "9:16"),
                    status=item.get("status", "review"),
                    theme=item.get("theme"),
                    preview_url=item.get("preview_url"),
                    video_url=item.get("video_url"),
                    created_at=parse_dt(item.get("created_at")),
                )
            )
        for item in data.get("point_ledger", []):
            db.add(
                PointLedger(
                    id=item["id"],
                    user_id=item["user_id"],
                    amount=int(item["amount"]),
                    type=item.get("type", "consume"),
                    scene=item.get("scene", ""),
                    description=item.get("description", ""),
                    balance_after=int(item.get("balance_after", 0)),
                    ai_job_id=item.get("ai_job_id"),
                    created_at=parse_dt(item.get("created_at")),
                )
            )
        db.commit()
