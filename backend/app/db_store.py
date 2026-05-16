from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from .config import DEFAULT_USAGE, STATUS_LABEL
from .db import SessionLocal
from .security import verify_password
from .utils import uid
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


def login_user(username: str, password: str, token: str, last_login: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username, User.status == "active"))
        if not user or not verify_password(password, user.password_hash):
            return None
        user.token = token
        user.last_login_at = _dt(last_login)
        db.commit()
        db.refresh(user)
        return _user_dict(user)


def register_user(username: str, display_name: str, password_hash: str, token: str, timestamp: str, bonus_points: int = 1000) -> dict[str, Any] | None:
    if SessionLocal is None:
        return None
    ts = _dt(timestamp)
    with SessionLocal() as db:
        user = User(
            id=uid("user"),
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            role="user",
            status="active",
            points=bonus_points,
            token=token,
            usage_json={},
            created_at=ts,
            last_login_at=ts,
        )
        db.add(user)
        db.add(
            PointLedger(
                id=uid("ledger"),
                user_id=user.id,
                amount=bonus_points,
                type="register_bonus",
                scene="注册赠送",
                description="新用户注册赠送积分",
                balance_after=bonus_points,
                created_at=ts,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
        return _user_dict(user)


def change_password(user_id: str, current_password: str, new_password: str) -> str:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return "missing"
        if not verify_password(current_password, user.password_hash):
            return "bad_password"
        from .security import hash_password
        user.password_hash = hash_password(new_password)
        db.commit()
        return "ok"


def admin_summary() -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT
                    (SELECT count(*) FROM users) AS user_count,
                    (SELECT count(*) FROM users WHERE status = 'active') AS active_user_count,
                    COALESCE((SELECT sum(points) FROM users), 0) AS total_balance,
                    COALESCE((SELECT -sum(amount) FROM point_ledger WHERE amount < 0), 0) AS consumed_points,
                    COALESCE((SELECT sum(amount) FROM point_ledger WHERE amount > 0), 0) AS granted_points,
                    (SELECT count(*) FROM point_ledger) AS ledger_count
                """
            )
        ).mappings().one()
        return {key: int(row[key] or 0) for key in row.keys()}


def admin_users() -> list[dict[str, Any]]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc()))
        return [_public_user_dict(user) for user in users]


def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        if role is not None:
            user.role = role
        if status is not None:
            user.status = status
        db.commit()
        db.refresh(user)
        return _public_user_dict(user)


def admin_reset_password(user_id: str, password_hash: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        user.password_hash = password_hash
        user.token = None
        db.commit()
        db.refresh(user)
        return _public_user_dict(user)


def admin_adjust_points(user_id: str, amount: int, reason: str, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        user.points = int(user.points or 0) + amount
        entry = PointLedger(
            id=uid("ledger"),
            user_id=user.id,
            amount=amount,
            type="admin_adjust",
            scene="管理员调整",
            description=reason,
            balance_after=user.points,
            created_at=_dt(timestamp),
        )
        db.add(entry)
        db.commit()
        db.refresh(user)
        return {"entry": _ledger_dict(entry, user), "user": _public_user_dict(user)}


def admin_point_ledger(user_id: str | None = None) -> list[dict[str, Any]]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        query = (
            select(PointLedger, User)
            .join(User, User.id == PointLedger.user_id)
            .order_by(PointLedger.created_at.desc())
            .limit(200)
        )
        if user_id:
            query = query.where(PointLedger.user_id == user_id)
        return [_ledger_dict(ledger, user) for ledger, user in db.execute(query).all()]


def _public_user_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "role": user.role or "user",
        "status": user.status or "active",
        "points": int(user.points or 0),
        "created_at": _fmt(user.created_at),
        "last_login": _fmt(user.last_login_at),
    }


def _ledger_dict(row: PointLedger, user: User | dict[str, Any]) -> dict[str, Any]:
    username = user.get("username", "") if isinstance(user, dict) else user.username
    display_name = user.get("display_name", "") if isinstance(user, dict) else user.display_name
    return {
        "id": row.id,
        "user_id": row.user_id,
        "username": username,
        "display_name": display_name,
        "amount": row.amount,
        "type": row.type,
        "scene": row.scene,
        "description": row.description or "",
        "balance_after": row.balance_after,
        "ai_job_id": row.ai_job_id,
        "created_at": _fmt(row.created_at),
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


def _change_points(db, user_id: str, amount: int, kind: str, scene: str, description: str, timestamp: datetime | None) -> PointLedger:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("missing_user")
    current = int(user.points or 0)
    if current + amount < 0:
        raise ValueError("insufficient_points")
    user.points = current + amount
    entry = PointLedger(
        id=uid("ledger"),
        user_id=user_id,
        amount=amount,
        type=kind,
        scene=scene,
        description=description,
        balance_after=user.points,
        created_at=timestamp,
    )
    db.add(entry)
    return entry


def _add_ai_job(
    db,
    user_id: str,
    job_type: str,
    provider: str,
    cost: int,
    timestamp: datetime | None,
    status: str = "succeeded",
    progress: int = 100,
    provider_task_id: str | None = None,
    error: str | None = None,
    **links,
) -> AiJob:
    job = AiJob(
        id=uid("job"),
        user_id=user_id,
        type=job_type,
        provider=provider,
        provider_task_id=provider_task_id,
        status=status,
        progress=progress,
        cost_points=cost,
        input_json={},
        output_json={},
        error=error,
        created_at=timestamp,
        updated_at=timestamp,
        completed_at=timestamp if status in {"succeeded", "failed", "cancelled"} else None,
        **{key: value for key, value in links.items() if value},
    )
    db.add(job)
    return job


def consume_with_job(
    user_id: str,
    amount: int,
    ledger_scene: str,
    ledger_description: str,
    job_type: str,
    provider: str,
    timestamp: str,
    status: str = "succeeded",
    progress: int = 100,
    provider_task_id: str | None = None,
    **links,
) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
    with SessionLocal() as db:
        try:
            _change_points(db, user_id, -amount, "consume", ledger_scene, ledger_description, ts)
        except ValueError as exc:
            return {"error": str(exc)}
        job = _add_ai_job(db, user_id, job_type, provider, amount, ts, status=status, progress=progress, provider_task_id=provider_task_id, **links)
        db.commit()
        return {"job": _ai_job_dict(job)}


def episode_generation_context(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        project = db.get(Project, episode.project_id)
        assets = list_assets(user, episode.project_id) or []
        shots = [_shot_dict(shot) for shot in db.scalars(select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.no))]
        return {
            "project": _project_dict(project) | {"owner": user.get("display_name", "")},
            "episode": _episode_dict(episode),
            "assets": assets,
            "shots": shots,
        }


def save_storyboard(
    user: dict[str, Any],
    episode_id: str,
    ai_shots: list[dict],
    generated_assets: list[dict],
    storyboard_cost: int,
    asset_cost: int,
    timestamp: str,
) -> list[dict[str, Any]] | dict[str, str] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
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
                _change_points(db, user["id"], -asset_cost, "consume", "AI 生成素材", f"AI 生成素材《{item['name']}》", ts)
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
                _add_ai_job(db, user["id"], "image_asset", "seedream", asset_cost, ts, project_id=episode.project_id, asset_id=asset.id)

            _change_points(db, user["id"], -storyboard_cost, "consume", "生成分镜", f"生成/更新《{episode.title}》分镜", ts)
            _add_ai_job(db, user["id"], "storyboard", "minimax", storyboard_cost, ts, episode_id=episode_id, project_id=episode.project_id)
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


def shot_generation_context(user: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
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
        assets = list_assets(user, episode.project_id) if episode else []
        return {
            "shot": _shot_dict(shot),
            "episode": _episode_dict(episode) if episode else None,
            "project": _project_dict(project) if project else None,
            "assets": assets or [],
        }


def create_video_task(user: dict[str, Any], shot_id: str, provider_task_id: str, cost_per_second: int, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
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
        duration = max(1, int(shot.duration))
        cost = duration * cost_per_second
        try:
            _change_points(db, user["id"], -cost, "consume", "生成镜头视频", f"生成镜头 #{shot.no}《{shot.title}》，{duration}s", ts)
        except ValueError as exc:
            return {"error": str(exc)}
        job = _add_ai_job(db, user["id"], "video_shot", "seedance", cost, ts, status="running", progress=0, provider_task_id=provider_task_id, episode_id=shot.episode_id, shot_id=shot.id, project_id=episode.project_id if episode else None)
        db.flush()
        task = db.scalar(select(VideoTask).where(VideoTask.shot_id == shot.id))
        if not task:
            task = VideoTask(id=uid("task"), episode_id=shot.episode_id, shot_id=shot.id, duration=duration, title=shot.title, progress=0, status="generating", updated_at=ts)
            db.add(task)
        task.title = shot.title
        task.duration = duration
        task.progress = 0
        task.status = "generating"
        task.provider = "seedance"
        task.provider_task_id = provider_task_id
        task.ai_job_id = job.id
        task.error = None
        task.updated_at = ts
        shot.status = "generating"
        shot.updated_at = ts
        if episode:
            episode.updated_at = ts
            project = db.get(Project, episode.project_id)
            if project:
                project.updated_at = ts
        db.commit()
        return _video_task_dict(task)


def workspace_bootstrap(user: dict[str, Any]) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

    with SessionLocal() as db:
        usage = {**(user.get("usage") or {})}
        for _k, _v in DEFAULT_USAGE.items():
            usage.setdefault(_k, _v)
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


def episode_workspace(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

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
                )
                SELECT
                    (SELECT count(*) FROM target_episode) AS found,
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
                        JOIN target_episode e ON e.id = s.episode_id
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
                        JOIN target_episode e ON e.id = t.episode_id
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
                        JOIN target_episode e ON e.project_id = v.project_id
                        WHERE v.episode_id = e.id
                    ), '[]'::jsonb) AS versions
                """
            ),
            {"episode_id": episode_id, "user_id": user["id"]},
        ).mappings().one()
        if int(row["found"] or 0) == 0:
            return None
        return {
            "shots": list(row["shots"] or []),
            "video_tasks": list(row["video_tasks"] or []),
            "versions": list(row["versions"] or []),
        }


def create_shot(user: dict[str, Any], episode_id: str, payload: Any, shot_id: str, updated_at: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

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
                "updated_at": _dt(updated_at),
            },
        ).mappings().first()
        db.commit()
        if not row or not row["shot"]:
            return None
        return dict(row["shot"])


def dashboard(user: dict[str, Any]) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

    with SessionLocal() as db:
        usage = {**(user.get("usage") or {})}
        for _k, _v in DEFAULT_USAGE.items():
            usage.setdefault(_k, _v)
        row = db.execute(
            text(
                """
                WITH user_projects AS (
                    SELECT id
                    FROM projects
                    WHERE owner_user_id = :user_id
                )
                SELECT
                    (SELECT count(*) FROM user_projects) AS project_count,
                    (SELECT count(*) FROM episodes e JOIN user_projects p ON p.id = e.project_id) AS episode_count,
                    (SELECT count(*) FROM assets a JOIN user_projects p ON p.id = a.project_id) AS asset_count,
                    (SELECT count(*) FROM video_versions v JOIN user_projects p ON p.id = v.project_id) AS version_count,
                    (SELECT count(*) FROM users WHERE status = 'active') AS team_members
                """
            ),
            {"user_id": user["id"]},
        ).mappings().one()
        usage["team_members"] = int(row["team_members"] or 0)
        return {
            "project_count": int(row["project_count"] or 0),
            "episode_count": int(row["episode_count"] or 0),
            "version_count": int(row["version_count"] or 0),
            "asset_count": int(row["asset_count"] or 0),
            "usage": usage,
            "current_user": user,
        }


def list_projects(user: dict[str, Any]) -> list[dict[str, Any]]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

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
                "updated_at": _fmt(row["updated_at"]),
                "episode_count": int(row["episode_count"] or 0),
                "asset_count": int(row["asset_count"] or 0),
                "version_count": int(row["version_count"] or 0),
            }
            for row in rows
        ]


def list_episodes(user: dict[str, Any], project_id: str) -> list[dict[str, Any]] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

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
                "updated_at": _fmt(row["updated_at"]),
                "shot_count": int(row["shot_count"] or 0),
                "version_count": int(row["version_count"] or 0),
            }
            for row in rows
        ]


def list_shots(user: dict[str, Any], episode_id: str) -> list[dict[str, Any]] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

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


def list_assets(user: dict[str, Any], project_id: str, asset_type: str | None = None) -> list[dict[str, Any]] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

    with SessionLocal() as db:
        owned = db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not owned:
            return None
        query = select(Asset).where(Asset.project_id == project_id)
        if asset_type:
            query = query.where(Asset.type == asset_type)
        asset_rows = list(db.scalars(query.order_by(Asset.updated_at.desc())))
        refs_by_asset: dict[str, list[dict]] = defaultdict(list)
        asset_ids = [asset.id for asset in asset_rows]
        if asset_ids:
            ref_rows = db.scalars(
                select(AssetReference)
                .where(AssetReference.asset_id.in_(asset_ids))
                .order_by(AssetReference.sort_order)
            )
            for ref in ref_rows:
                refs_by_asset[ref.asset_id].append(
                    {
                        "id": ref.id,
                        "type": ref.type,
                        "name": ref.name,
                        "url": ref.url,
                        "note": ref.note,
                    }
                )
        return [_asset_dict(asset, refs_by_asset.get(asset.id, [])) for asset in asset_rows]


def list_video_versions(user: dict[str, Any], project_id: str, episode_id: str | None = None) -> list[dict[str, Any]] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

    with SessionLocal() as db:
        owned = db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not owned:
            return None
        query = select(VideoVersion).where(VideoVersion.project_id == project_id)
        if episode_id:
            query = query.where(VideoVersion.episode_id == episode_id)
        rows = db.scalars(query.order_by(VideoVersion.created_at.desc()))
        return [_video_version_dict(row) for row in rows]


def point_ledger(user: dict[str, Any], page: int = 1, page_size: int = 10) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")

    safe_page = max(1, page)
    safe_size = min(100, max(1, page_size))
    offset = (safe_page - 1) * safe_size
    with SessionLocal() as db:
        total = db.query(PointLedger).filter(PointLedger.user_id == user["id"]).count()
        rows = db.scalars(
            select(PointLedger)
            .where(PointLedger.user_id == user["id"])
            .order_by(PointLedger.created_at.desc())
            .offset(offset)
            .limit(safe_size)
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "username": user.get("username", ""),
                    "display_name": user.get("display_name", ""),
                    "amount": row.amount,
                    "type": row.type,
                    "scene": row.scene,
                    "description": row.description or "",
                    "balance_after": row.balance_after,
                    "ai_job_id": row.ai_job_id,
                    "created_at": _fmt(row.created_at),
                }
                for row in rows
            ],
            "total": total,
        }


def get_project(user: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    projects = list_projects(user)
    return next((project for project in projects if project["id"] == project_id), None)


def create_project(user: dict[str, Any], payload: Any, timestamp: str) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
    project = Project(
        id=uid("proj"),
        owner_user_id=user["id"],
        name=payload.name.strip(),
        short_name=payload.name.strip()[:8],
        description=payload.description,
        status="draft",
        cover="dark",
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


def update_project(user: dict[str, Any], project_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
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
        project.updated_at = _dt(timestamp)
        db.commit()
        return get_project(user, project_id)


def delete_project(user: dict[str, Any], project_id: str) -> bool:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not project:
            return False
        db.delete(project)
        db.commit()
        return True


def get_episode(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        shot_count = db.query(Shot).filter(Shot.episode_id == episode.id).count()
        version_count = db.query(VideoVersion).filter(VideoVersion.episode_id == episode.id).count()
        return _episode_dict(episode, shot_count, version_count)


def create_episode(user: dict[str, Any], project_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
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


def update_episode(user: dict[str, Any], episode_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
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


def delete_episode(user: dict[str, Any], episode_id: str, timestamp: str) -> tuple[bool, str | None]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
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
            project.updated_at = _dt(timestamp)
        db.commit()
        return True, project_id


def patch_shot(user: dict[str, Any], shot_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
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
        task = db.scalar(select(VideoTask).where(VideoTask.shot_id == shot_id))
        if task:
            if "title" in updates:
                task.title = shot.title
            if "duration" in updates:
                task.duration = shot.duration
            task.updated_at = ts
        episode = db.get(Episode, shot.episode_id)
        if episode:
            episode.updated_at = ts
            project = db.get(Project, episode.project_id)
            if project:
                project.updated_at = ts
        db.commit()
        return _shot_dict(shot)


def delete_shot(user: dict[str, Any], shot_id: str, timestamp: str) -> bool:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
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
            episode.updated_at = _dt(timestamp)
            project = db.get(Project, episode.project_id)
            if project:
                project.updated_at = episode.updated_at
        db.commit()
        return True


def create_asset(user: dict[str, Any], project_id: str, payload: Any, refs: list[dict], cost: int, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
    visual_asset = payload.type in {"character", "scene", "image"}
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        target_user = db.get(User, user["id"])
        if not project or not target_user:
            return None
        if target_user.points - cost < 0:
            return {"error": "points"}
        target_user.points -= cost
        asset = Asset(
            id=uid("asset"),
            project_id=project_id,
            type=payload.type,
            name=payload.name,
            description=payload.description,
            initial=(payload.initial[:1] or payload.name[:1]),
            image_url=payload.image,
            voice_label=payload.voice,
            voice_url=payload.voice_url,
            voice_status="uploaded" if payload.voice_url else None,
            provider_meta={},
            updated_at=ts,
        )
        db.add(asset)
        db.flush()
        for index, ref in enumerate(refs):
            db.add(
                AssetReference(
                    id=ref.get("id") or uid("ref"),
                    asset_id=asset.id,
                    type=ref.get("type", "image"),
                    name=ref.get("name") or f"参考 {index + 1}",
                    url=ref.get("url"),
                    note=ref.get("note"),
                    sort_order=index,
                )
            )
        db.add(PointLedger(id=uid("ledger"), user_id=user["id"], amount=-cost, type="consume", scene="创建素材", description=f"创建素材《{payload.name}》", balance_after=target_user.points, created_at=ts))
        if visual_asset:
            usage = dict(target_user.usage_json or {})
            usage.setdefault("image_total", 1000)
            usage.setdefault("image_used", 0)
            usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)
            target_user.usage_json = usage
        project.updated_at = ts
        db.commit()
        return _asset_dict(asset, refs)


def generate_asset(user: dict[str, Any], project_id: str, payload: Any, generated_url: str | None, refs: list[dict], cost: int, provider: str, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
    visual_asset = payload.type in {"character", "scene", "image"}
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        target_user = db.get(User, user["id"])
        if not project or not target_user:
            return None
        try:
            _change_points(db, user["id"], -cost, "consume", "AI 生成素材", f"AI 生成素材《{payload.name}》", ts)
        except ValueError as exc:
            return {"error": str(exc)}
        asset = Asset(
            id=uid("asset"),
            project_id=project_id,
            type=payload.type,
            name=payload.name,
            description=payload.description,
            initial=payload.name[:1],
            image_url=generated_url,
            voice_label=None,
            voice_url=None,
            provider_meta={},
            updated_at=ts,
        )
        db.add(asset)
        db.flush()
        for index, ref in enumerate(refs):
            db.add(AssetReference(id=ref.get("id") or uid("ref"), asset_id=asset.id, type=ref.get("type", "image"), name=ref.get("name", f"参考 {index + 1}"), url=ref.get("url"), note=ref.get("note"), sort_order=index))
        _add_ai_job(db, user["id"], "image_asset" if visual_asset else "audio_asset", provider, cost, ts, project_id=project_id, asset_id=asset.id)
        if visual_asset:
            usage = dict(target_user.usage_json or {})
            usage.setdefault("image_total", 1000)
            usage.setdefault("image_used", 0)
            usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)
            target_user.usage_json = usage
        project.updated_at = ts
        db.commit()
        return _asset_dict(asset, refs)


def update_asset(user: dict[str, Any], asset_id: str, payload: Any, refs: list[dict] | None, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
    with SessionLocal() as db:
        asset = db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return None
        updates = payload.model_dump(exclude_unset=True)
        field_map = {
            "name": "name",
            "description": "description",
            "initial": "initial",
            "image": "image_url",
            "voice": "voice_label",
            "voice_url": "voice_url",
            "voice_status": "voice_status",
            "speaker_id": "speaker_id",
        }
        for source, target in field_map.items():
            if source in updates:
                value = updates[source]
                if source == "initial" and value:
                    value = value[:1]
                setattr(asset, target, value)
        asset.updated_at = ts
        if refs is not None:
            db.execute(delete(AssetReference).where(AssetReference.asset_id == asset_id))
            for index, ref in enumerate(refs):
                db.add(
                    AssetReference(
                        id=ref.get("id") or uid("ref"),
                        asset_id=asset_id,
                        type=ref.get("type", "image"),
                        name=ref.get("name") or f"参考 {index + 1}",
                        url=ref.get("url"),
                        note=ref.get("note"),
                        sort_order=index,
                    )
                )
        project = db.get(Project, asset.project_id)
        if project:
            project.updated_at = ts
        db.commit()
        ref_dicts = refs if refs is not None else [
            {"id": ref.id, "type": ref.type, "name": ref.name, "url": ref.url, "note": ref.note}
            for ref in db.scalars(select(AssetReference).where(AssetReference.asset_id == asset_id).order_by(AssetReference.sort_order))
        ]
        return _asset_dict(asset, ref_dicts)


def delete_asset(user: dict[str, Any], asset_id: str) -> bool:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        asset = db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return False
        db.delete(asset)
        db.commit()
        return True


def delete_video_version(user: dict[str, Any], version_id: str) -> bool:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        version = db.scalar(
            select(VideoVersion)
            .join(Project, Project.id == VideoVersion.project_id)
            .where(VideoVersion.id == version_id, Project.owner_user_id == user["id"])
        )
        if not version:
            return False
        db.delete(version)
        db.commit()
        return True


def get_asset(user: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        asset = db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return None
        refs = [
            {"id": ref.id, "type": ref.type, "name": ref.name, "url": ref.url, "note": ref.note}
            for ref in db.scalars(select(AssetReference).where(AssetReference.asset_id == asset_id).order_by(AssetReference.sort_order))
        ]
        return _asset_dict(asset, refs)


def update_voice_clone(user: dict[str, Any], asset_id: str, result: dict[str, Any], cost: int, timestamp: str, consume: bool = True) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
    with SessionLocal() as db:
        asset = db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return None
        if consume:
            try:
                _change_points(db, user["id"], -cost, "consume", "音色克隆", f"训练《{asset.name}》角色音色", ts)
            except ValueError as exc:
                return {"error": str(exc)}
        for key, attr in {"speaker_id": "speaker_id", "voice_url": "voice_url", "voice_status": "voice_status", "error": None}.items():
            if key in result and attr:
                setattr(asset, attr, result[key])
        asset.updated_at = ts
        if consume:
            _add_ai_job(
                db,
                user["id"],
                "voice_clone",
                "volc_voice",
                cost,
                ts,
                status="succeeded" if asset.voice_status == "completed" else "running",
                progress=100 if asset.voice_status == "completed" else 0,
                provider_task_id=asset.speaker_id,
                project_id=asset.project_id,
                asset_id=asset_id,
            )
        db.commit()
        return _asset_dict(asset)


def compose_context(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    context = episode_generation_context(user, episode_id)
    if not context:
        return None
    with SessionLocal() as db:
        tasks = [_video_task_dict(task) for task in db.scalars(select(VideoTask).where(VideoTask.episode_id == episode_id))]
    context["video_tasks"] = tasks
    return context


def save_composed_version(user: dict[str, Any], episode_id: str, payload: Any, video_url: str, cost: int, timestamp: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    ts = _dt(timestamp)
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        try:
            _change_points(db, user["id"], -cost, "consume", "合成成片", f"合成《{episode.title}》成片版本", ts)
        except ValueError as exc:
            return {"error": str(exc)}
        _add_ai_job(db, user["id"], "compose", "ffmpeg", cost, ts, episode_id=episode_id, project_id=episode.project_id)
        version_no = db.query(VideoVersion).filter(VideoVersion.episode_id == episode_id).count() + 1
        version = VideoVersion(
            id=uid("ver"),
            project_id=episode.project_id,
            episode_id=episode_id,
            name=payload.name if payload.name != "成片版本" else f"第{episode.no:02d}集 版本{chr(64 + version_no)}",
            description=payload.description,
            duration=payload.duration,
            ratio=payload.ratio,
            status="exported",
            theme="green" if version_no % 2 else "blue",
            preview_url=video_url,
            video_url=video_url,
            created_at=ts,
        )
        db.add(version)
        target_user = db.get(User, user["id"])
        if target_user:
            usage_data = dict(target_user.usage_json or {})
            usage_data.setdefault("export_total", 164)
            usage_data.setdefault("export_used", 0)
            usage_data["export_used"] = min(usage_data["export_total"], usage_data["export_used"] + 1)
            target_user.usage_json = usage_data
        episode.updated_at = ts
        project = db.get(Project, episode.project_id)
        if project:
            project.updated_at = ts
        db.commit()
        return _video_version_dict(version)


def usage(user: dict[str, Any]) -> dict[str, Any]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        db_user = db.get(User, user["id"])
        usage_data = dict((db_user.usage_json if db_user else user.get("usage")) or {})
        for _k, _v in DEFAULT_USAGE.items():
            usage_data.setdefault(_k, _v)
        usage_data["team_members"] = db.query(User).filter(User.status == "active").count()
        return usage_data


def get_ai_job(user: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        job = db.get(AiJob, job_id)
        if not job:
            return None
        if job.user_id != user["id"] and user.get("role") != "admin":
            return {"error": "forbidden"}
        return _ai_job_dict(job)


def list_project_ai_jobs(user: dict[str, Any], project_id: str) -> list[dict[str, Any]] | None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as db:
        owned = db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not owned:
            return None
        jobs = db.scalars(select(AiJob).where(AiJob.project_id == project_id).order_by(AiJob.created_at.desc()).limit(100))
        return [_ai_job_dict(job) for job in jobs]


def _ai_job_dict(job: AiJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "user_id": job.user_id,
        "project_id": job.project_id,
        "episode_id": job.episode_id,
        "shot_id": job.shot_id,
        "asset_id": job.asset_id,
        "type": job.type,
        "provider": job.provider,
        "provider_task_id": job.provider_task_id,
        "status": job.status,
        "progress": job.progress,
        "input_json": job.input_json or {},
        "output_json": job.output_json or {},
        "error": job.error,
        "cost_points": job.cost_points,
        "created_at": _fmt(job.created_at),
        "updated_at": _fmt(job.updated_at),
        "completed_at": _fmt(job.completed_at),
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
