from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, text

from .config import STATUS_LABEL
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
    VideoTask,
    VideoVersion,
)


def enabled() -> bool:
    return SessionLocal is not None


def _user_dict(row: User) -> dict[str, Any]:
    return {
        "id": row.id,
        "username": row.username,
        "display_name": row.display_name,
        "password_hash": row.password_hash,
        "role": row.role,
        "status": row.status,
        "points": row.points,
        "token": row.token or "",
        "usage": row.usage_json or {},
        "created_at": _fmt(row.created_at),
        "last_login": _fmt(row.last_login_at),
    }


def find_user_by_token(token: str | None) -> dict[str, Any] | None:
    if SessionLocal is None or not token:
        return None
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.token == token))
        return _user_dict(user) if user else None


def find_user_by_username(username: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        return _user_dict(user) if user else None


def update_user_login(user_id: str, token: str, last_login: str) -> None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return
        user.token = token
        user.last_login_at = _dt(last_login)
        db.commit()


def login_user(username: str, password_hash: str, token: str, last_login: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                UPDATE users
                SET token = :token,
                    last_login_at = :last_login
                WHERE username = :username
                  AND password_hash = :password_hash
                  AND status = 'active'
                RETURNING id, username, display_name, password_hash, role, status, points, token, usage_json, created_at, last_login_at
                """
            ),
            {
                "username": username,
                "password_hash": password_hash,
                "token": token,
                "last_login": _dt(last_login),
            },
        ).mappings().first()
        db.commit()
        if not row:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "status": row["status"],
            "points": row["points"],
            "token": row["token"] or "",
            "usage": row["usage_json"] or {},
            "created_at": _fmt(row["created_at"]),
            "last_login": _fmt(row["last_login_at"]),
        }


def _project_dict(row: Project, episode_count: int = 0, asset_count: int = 0, version_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "owner_user_id": row.owner_user_id,
        "owner": "",
        "name": row.name,
        "short_name": row.short_name,
        "description": row.description or "",
        "status": row.status,
        "status_label": STATUS_LABEL.get(row.status, row.status),
        "cover": row.cover,
        "cover_image": row.cover_image_url,
        "updated_at": _fmt(row.updated_at),
        "episode_count": episode_count,
        "asset_count": asset_count,
        "version_count": version_count,
    }


def _episode_dict(row: Episode, shot_count: int = 0, version_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "no": row.no,
        "title": row.title,
        "summary": row.summary or "",
        "script": row.script or "",
        "duration_target": row.duration_target,
        "status": row.status,
        "status_label": STATUS_LABEL.get(row.status, row.status),
        "updated_at": _fmt(row.updated_at),
        "shot_count": shot_count,
        "version_count": version_count,
    }


def _shot_dict(row: Shot) -> dict[str, Any]:
    return {
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
        "updated_at": _fmt(row.updated_at),
    }


def _asset_dict(row: Asset, refs: list[dict] | None = None) -> dict[str, Any]:
    references = refs or []
    return {
        "id": row.id,
        "project_id": row.project_id,
        "type": row.type,
        "name": row.name,
        "description": row.description or "",
        "ref_count": len(references),
        "initial": row.initial or row.name[:1],
        "image": row.image_url,
        "voice": row.voice_label,
        "voice_url": row.voice_url,
        "speaker_id": row.speaker_id,
        "voice_status": row.voice_status,
        "references": references,
        "updated_at": _fmt(row.updated_at),
    }


def _video_task_dict(row: VideoTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "episode_id": row.episode_id,
        "shot_id": row.shot_id,
        "ai_job_id": row.ai_job_id,
        "title": row.title,
        "duration": row.duration,
        "progress": row.progress,
        "status": row.status,
        "provider": row.provider,
        "provider_task_id": row.provider_task_id,
        "preview_url": row.preview_url,
        "video_url": row.video_url,
        "error": row.error,
        "updated_at": _fmt(row.updated_at),
    }


def _video_version_dict(row: VideoVersion) -> dict[str, Any]:
    return {
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
        "created_at": _fmt(row.created_at),
    }


def workspace_bootstrap(user: dict[str, Any]) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

    with SessionLocal() as db:
        usage = {**(user.get("usage") or {})}
        usage.setdefault("video_total_seconds", 2000)
        usage.setdefault("video_used_seconds", 0)
        usage.setdefault("image_total", 1000)
        usage.setdefault("image_used", 0)
        usage.setdefault("export_total", 164)
        usage.setdefault("export_used", 0)
        row = db.execute(
            text(
                """
                WITH user_projects AS (
                    SELECT *
                    FROM projects
                    WHERE owner_user_id = :user_id
                ),
                first_project AS (
                    SELECT id
                    FROM user_projects
                    ORDER BY updated_at DESC
                    LIMIT 1
                ),
                first_episodes AS (
                    SELECT e.*
                    FROM episodes e
                    JOIN first_project fp ON fp.id = e.project_id
                ),
                first_episode AS (
                    SELECT id
                    FROM first_episodes
                    ORDER BY no
                    LIMIT 1
                )
                SELECT
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', p.id,
                                'owner_user_id', p.owner_user_id,
                                'owner', CAST(:display_name AS text),
                                'name', p.name,
                                'short_name', p.short_name,
                                'description', COALESCE(p.description, ''),
                                'status', p.status,
                                'cover', p.cover,
                                'cover_image', p.cover_image_url,
                                'updated_at', p.updated_at,
                                'episode_count', (SELECT count(*) FROM episodes e WHERE e.project_id = p.id),
                                'asset_count', (SELECT count(*) FROM assets a WHERE a.project_id = p.id),
                                'version_count', (SELECT count(*) FROM video_versions v WHERE v.project_id = p.id)
                            )
                            ORDER BY p.updated_at DESC
                        )
                        FROM user_projects p
                    ), '[]'::jsonb) AS projects,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', e.id,
                                'project_id', e.project_id,
                                'no', e.no,
                                'title', e.title,
                                'summary', COALESCE(e.summary, ''),
                                'script', COALESCE(e.script, ''),
                                'duration_target', e.duration_target,
                                'status', e.status,
                                'updated_at', e.updated_at,
                                'shot_count', (SELECT count(*) FROM shots s WHERE s.episode_id = e.id),
                                'version_count', (SELECT count(*) FROM video_versions v WHERE v.episode_id = e.id)
                            )
                            ORDER BY e.no
                        )
                        FROM first_episodes e
                    ), '[]'::jsonb) AS episodes,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', a.id,
                                'project_id', a.project_id,
                                'type', a.type,
                                'name', a.name,
                                'description', COALESCE(a.description, ''),
                                'initial', COALESCE(NULLIF(a.initial, ''), LEFT(a.name, 1)),
                                'image', a.image_url,
                                'voice', a.voice_label,
                                'voice_url', a.voice_url,
                                'speaker_id', a.speaker_id,
                                'voice_status', a.voice_status,
                                'updated_at', a.updated_at,
                                'references', COALESCE((
                                    SELECT jsonb_agg(
                                        jsonb_build_object(
                                            'id', ar.id,
                                            'type', ar.type,
                                            'name', ar.name,
                                            'url', ar.url,
                                            'note', ar.note
                                        )
                                        ORDER BY ar.sort_order
                                    )
                                    FROM asset_references ar
                                    WHERE ar.asset_id = a.id
                                ), '[]'::jsonb),
                                'ref_count', (
                                    SELECT count(*)
                                    FROM asset_references ar
                                    WHERE ar.asset_id = a.id
                                )
                            )
                            ORDER BY a.updated_at DESC
                        )
                        FROM assets a
                        JOIN first_project fp ON fp.id = a.project_id
                    ), '[]'::jsonb) AS assets,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', s.id,
                                'episode_id', s.episode_id,
                                'no', s.no,
                                'title', s.title,
                                'visual', COALESCE(s.visual, ''),
                                'dialogue', COALESCE(s.dialogue, ''),
                                'characters', s.characters,
                                'scene', COALESCE(s.scene, ''),
                                'duration', s.duration,
                                'status', s.status,
                                'updated_at', s.updated_at
                            )
                            ORDER BY s.no
                        )
                        FROM shots s
                        JOIN first_episode fe ON fe.id = s.episode_id
                    ), '[]'::jsonb) AS shots,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', t.id,
                                'episode_id', t.episode_id,
                                'shot_id', t.shot_id,
                                'ai_job_id', t.ai_job_id,
                                'title', t.title,
                                'duration', t.duration,
                                'progress', t.progress,
                                'status', t.status,
                                'provider', t.provider,
                                'provider_task_id', t.provider_task_id,
                                'preview_url', t.preview_url,
                                'video_url', t.video_url,
                                'error', t.error,
                                'updated_at', t.updated_at
                            )
                            ORDER BY t.updated_at DESC
                        )
                        FROM video_tasks t
                        JOIN first_episode fe ON fe.id = t.episode_id
                    ), '[]'::jsonb) AS video_tasks,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', v.id,
                                'project_id', v.project_id,
                                'episode_id', v.episode_id,
                                'name', v.name,
                                'description', COALESCE(v.description, ''),
                                'duration', v.duration,
                                'ratio', v.ratio,
                                'status', v.status,
                                'theme', v.theme,
                                'preview_url', v.preview_url,
                                'video_url', v.video_url,
                                'created_at', v.created_at
                            )
                            ORDER BY v.created_at DESC
                        )
                        FROM video_versions v
                        JOIN first_project fp ON fp.id = v.project_id
                        WHERE NOT EXISTS (SELECT 1 FROM first_episode)
                           OR v.episode_id = (SELECT id FROM first_episode)
                    ), '[]'::jsonb) AS versions,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', l.id,
                                'user_id', l.user_id,
                                'username', CAST(:username AS text),
                                'display_name', CAST(:display_name AS text),
                                'amount', l.amount,
                                'type', l.type,
                                'scene', l.scene,
                                'description', COALESCE(l.description, ''),
                                'balance_after', l.balance_after,
                                'ai_job_id', l.ai_job_id,
                                'created_at', l.created_at
                            )
                            ORDER BY l.created_at DESC
                        )
                        FROM (
                            SELECT *
                            FROM point_ledger
                            WHERE user_id = :user_id
                            ORDER BY created_at DESC
                            LIMIT 10
                        ) l
                    ), '[]'::jsonb) AS ledger,
                    (SELECT count(*) FROM user_projects) AS project_count,
                    (SELECT count(*) FROM episodes e JOIN user_projects p ON p.id = e.project_id) AS episode_count,
                    (SELECT count(*) FROM assets a JOIN user_projects p ON p.id = a.project_id) AS asset_count,
                    (SELECT count(*) FROM video_versions v JOIN user_projects p ON p.id = v.project_id) AS version_count,
                    (SELECT count(*) FROM point_ledger WHERE user_id = :user_id) AS ledger_total,
                    (SELECT count(*) FROM users WHERE status = 'active') AS team_members
                """
            ),
            {
                "user_id": user["id"],
                "username": user.get("username", ""),
                "display_name": user.get("display_name", ""),
            },
        ).mappings().one()

        projects = list(row["projects"] or [])
        project_episodes = list(row["episodes"] or [])
        project_assets = list(row["assets"] or [])
        episode_shots = list(row["shots"] or [])
        episode_tasks = list(row["video_tasks"] or [])
        project_versions = list(row["versions"] or [])
        ledger = list(row["ledger"] or [])

        for project in projects:
            project["status_label"] = STATUS_LABEL.get(project.get("status"), project.get("status"))
        for episode in project_episodes:
            episode["status_label"] = STATUS_LABEL.get(episode.get("status"), episode.get("status"))
        usage["team_members"] = int(row["team_members"] or 0)
        current_project = projects[0] if projects else None
        selected_episode = project_episodes[0] if project_episodes else None

        return {
            "dashboard": {
                "project_count": int(row["project_count"] or 0),
                "episode_count": int(row["episode_count"] or 0),
                "version_count": int(row["version_count"] or 0),
                "asset_count": int(row["asset_count"] or 0),
                "usage": usage,
                "current_user": user,
            },
            "point_ledger": {"items": ledger, "total": int(row["ledger_total"] or 0)},
            "projects": projects,
            "current_project": current_project,
            "episodes": project_episodes,
            "selected_episode": selected_episode,
            "shots": episode_shots,
            "assets": project_assets,
            "video_tasks": episode_tasks,
            "versions": project_versions,
        }


def _fmt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value or ""


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value), pattern)
        except ValueError:
            pass
    return None


def load_data() -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
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
                "updated_at": _fmt(row.updated_at),
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
                "updated_at": _fmt(row.updated_at),
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
                "updated_at": _fmt(row.updated_at),
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
                "updated_at": _fmt(row.updated_at),
            }
            for row in db.scalars(select(Asset))
        ]
        video_tasks = [
            {
                "id": row.id,
                "episode_id": row.episode_id,
                "shot_id": row.shot_id,
                "ai_job_id": row.ai_job_id,
                "title": row.title,
                "duration": row.duration,
                "progress": row.progress,
                "status": row.status,
                "provider": row.provider,
                "provider_task_id": row.provider_task_id,
                "preview_url": row.preview_url,
                "video_url": row.video_url,
                "error": row.error,
                "updated_at": _fmt(row.updated_at),
            }
            for row in db.scalars(select(VideoTask))
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
                "created_at": _fmt(row.created_at),
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
                    "created_at": _fmt(row.created_at),
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
                "created_at": _fmt(row.created_at),
                "updated_at": _fmt(row.updated_at),
                "completed_at": _fmt(row.completed_at),
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
                "created_at": _fmt(row.created_at),
                "last_login": _fmt(row.last_login_at),
            }
            for row in users
        ]
        usage = {
            "video_total_seconds": 2000,
            "video_used_seconds": sum((user.usage_json or {}).get("video_used_seconds", 0) for user in users),
            "image_total": 1000,
            "image_used": sum((user.usage_json or {}).get("image_used", 0) for user in users),
            "export_total": 164,
            "export_used": sum((user.usage_json or {}).get("export_used", 0) for user in users),
            "team_members": len([user for user in users if user.status == "active"]),
        }
        return {
            "projects": projects,
            "episodes": episodes,
            "shots": shots,
            "assets": assets,
            "video_tasks": video_tasks,
            "video_versions": video_versions,
            "usage": usage,
            "users": user_rows,
            "point_ledger": point_ledger,
            "ai_jobs": ai_jobs,
        }


def save_data(data: dict[str, Any]) -> None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        for model in [PointLedger, VideoVersion, VideoTask, AiJob, AssetReference, Asset, Shot, Episode, Project]:
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
                    created_at=_dt(item.get("created_at")),
                    last_login_at=_dt(item.get("last_login")),
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
                    updated_at=_dt(item.get("updated_at")),
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
                    updated_at=_dt(item.get("updated_at")),
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
                    updated_at=_dt(item.get("updated_at")),
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
                    updated_at=_dt(item.get("updated_at")),
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
                    created_at=_dt(item.get("created_at")),
                    updated_at=_dt(item.get("updated_at")),
                    completed_at=_dt(item.get("completed_at")),
                )
            )
        db.flush()
        for item in data.get("video_tasks", []):
            db.add(
                VideoTask(
                    id=item["id"],
                    episode_id=item["episode_id"],
                    shot_id=item["shot_id"],
                    ai_job_id=item.get("ai_job_id"),
                    title=item["title"],
                    duration=int(item.get("duration", 1)),
                    progress=int(item.get("progress", 0)),
                    status=item.get("status", "pending"),
                    provider=item.get("provider"),
                    provider_task_id=item.get("provider_task_id"),
                    preview_url=item.get("preview_url"),
                    video_url=item.get("video_url"),
                    error=item.get("error"),
                    updated_at=_dt(item.get("updated_at")),
                )
            )
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
                    created_at=_dt(item.get("created_at")),
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
                    created_at=_dt(item.get("created_at")),
                )
            )
        db.commit()
