from __future__ import annotations

import functools

def require_db(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if SessionLocal is None:
            raise RuntimeError("DATABASE_URL is not configured")
        return func(*args, **kwargs)
    return wrapper


from collections import defaultdict
from datetime import datetime
import json
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from .config import DEFAULT_USAGE, STATUS_LABEL, apply_usage_defaults
from .db import SessionLocal
from .security import verify_password
from .serializers import (
    _ai_job_dict,
    _asset_dict,
    _episode_dict,
    _ledger_dict,
    _project_dict,
    _shot_dict,
    _user_dict,
    _video_task_dict,
    _video_version_dict,
)
from .utils import uid, fmt_dt, parse_dt, public_user_dict
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


@require_db
def find_user_by_token(token: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.token == token))
        return _user_dict(user) if user else None


@require_db
def find_user_by_username(username: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        return _user_dict(user) if user else None


@require_db
def get_public_user(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return public_user_dict(user) if user else None


@require_db
def user_has_points(user_id: str, cost: int) -> bool:
    if cost <= 0:
        return True
    with SessionLocal() as db:
        points = db.scalar(select(User.points).where(User.id == user_id))
        return points is not None and int(points or 0) >= cost


@require_db
def update_user_login(user_id: str, token: str, last_login: str) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return
        user.token = token
        user.last_login_at = parse_dt(last_login)
        db.commit()


@require_db
def login_user(username: str, password: str, token: str, last_login: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username, User.status == "active"))
        if not user or not verify_password(password, user.password_hash):
            return None
        user.token = token
        user.last_login_at = parse_dt(last_login)
        db.commit()
        db.refresh(user)
        return _user_dict(user)


@require_db
def register_user(username: str, display_name: str, password_hash: str, token: str, timestamp: str, bonus_points: int = 1000) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
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


@require_db
def change_password(user_id: str, current_password: str, new_password: str) -> str:
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


@require_db
def admin_summary() -> dict[str, Any]:
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


@require_db
def admin_users() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc()))
        return [public_user_dict(user) for user in users]


@require_db
def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict[str, Any] | None:
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
        return public_user_dict(user)


@require_db
def admin_reset_password(user_id: str, password_hash: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        user.password_hash = password_hash
        user.token = None
        db.commit()
        db.refresh(user)
        return public_user_dict(user)


@require_db
def admin_adjust_points(user_id: str, amount: int, reason: str, timestamp: str) -> dict[str, Any] | None:
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
            created_at=parse_dt(timestamp),
        )
        db.add(entry)
        db.commit()
        db.refresh(user)
        return {"entry": _ledger_dict(entry, user), "user": public_user_dict(user)}


@require_db
def admin_point_ledger(user_id: str | None = None) -> list[dict[str, Any]]:
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



def _change_points(db, user_id: str, amount: int, kind: str, scene: str, description: str, timestamp: datetime | None) -> PointLedger:
    user = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
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


@require_db
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
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        try:
            _change_points(db, user_id, -amount, "consume", ledger_scene, ledger_description, ts)
        except ValueError as exc:
            return {"error": str(exc)}
        job = _add_ai_job(db, user_id, job_type, provider, amount, ts, status=status, progress=progress, provider_task_id=provider_task_id, **links)
        db.commit()
        return {"job": _ai_job_dict(job)}


@require_db
def episode_generation_context(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
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
) -> list[dict[str, Any]] | dict[str, str] | None:
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
def create_video_task(user: dict[str, Any], shot_id: str, provider_task_id: str, cost_per_second: int, timestamp: str) -> dict[str, Any] | None:
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


@require_db
def batch_create_video_tasks(user: dict[str, Any], provider_tasks: dict[str, str], cost_per_second: int, timestamp: str) -> tuple[list[dict], str | None]:
    """Create multiple video tasks in a single transaction.

    Returns (tasks, error). If any shot fails due to insufficient points,
    returns the error string and no tasks are created.
    """
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        tasks = []
        for shot_id, provider_task_id in provider_tasks.items():
            shot = db.scalar(
                select(Shot)
                .join(Episode, Episode.id == Shot.episode_id)
                .join(Project, Project.id == Episode.project_id)
                .where(Shot.id == shot_id, Project.owner_user_id == user["id"])
            )
            if not shot:
                continue
            episode = db.get(Episode, shot.episode_id)
            duration = max(1, int(shot.duration))
            cost = duration * cost_per_second
            try:
                _change_points(db, user["id"], -cost, "consume", "生成镜头视频", f"生成镜头 #{shot.no}《{shot.title}》，{duration}s", ts)
            except ValueError as exc:
                db.rollback()
                return [], str(exc)
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
            tasks.append(task)
        db.commit()
        return [_video_task_dict(t) for t in tasks], None


@require_db
def update_video_task_from_provider(task: dict[str, Any], remote: dict[str, Any]) -> None:
    """Update a video task dict (and its DB row) from remote provider data."""
    updated = {k: v for k, v in remote.items() if v is not None}
    task.update(updated)
    ts = datetime.now()
    task["updated_at"] = ts.isoformat()
    with SessionLocal() as db:
        row = db.get(VideoTask, task["id"])
        if not row:
            return
        for key in ("progress", "status", "preview_url", "video_url", "error"):
            if key in updated:
                setattr(row, key, updated[key])
        row.updated_at = ts
        if task.get("status") in {"completed", "failed"}:
            shot = db.get(Shot, row.shot_id)
            if shot:
                shot.status = task["status"]
                shot.updated_at = ts
            if row.ai_job_id:
                job = db.get(AiJob, row.ai_job_id)
                if job:
                    job.progress = task.get("progress", job.progress)
                    job.updated_at = ts
                    if task["status"] == "completed":
                        job.status = "succeeded"
                        job.completed_at = ts
                        job.output_json = json.dumps({"video_url": task.get("video_url")})
                    else:
                        job.status = "failed"
                        job.error = task.get("error")
                        job.completed_at = ts
        db.commit()


@require_db
def workspace_bootstrap(user: dict[str, Any]) -> dict[str, Any]:

    with SessionLocal() as db:
        usage = apply_usage_defaults({**(user.get("usage") or {})})
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


@require_db
def episode_workspace(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:

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
def dashboard(user: dict[str, Any]) -> dict[str, Any]:

    with SessionLocal() as db:
        usage = apply_usage_defaults({**(user.get("usage") or {})})
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
                "updated_at": fmt_dt(row["updated_at"]),
                "episode_count": int(row["episode_count"] or 0),
                "asset_count": int(row["asset_count"] or 0),
                "version_count": int(row["version_count"] or 0),
            }
            for row in rows
        ]


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
def list_assets(user: dict[str, Any], project_id: str, asset_type: str | None = None) -> list[dict[str, Any]] | None:

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


@require_db
def list_video_versions(user: dict[str, Any], project_id: str, episode_id: str | None = None) -> list[dict[str, Any]] | None:

    with SessionLocal() as db:
        owned = db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not owned:
            return None
        query = select(VideoVersion).where(VideoVersion.project_id == project_id)
        if episode_id:
            query = query.where(VideoVersion.episode_id == episode_id)
        rows = db.scalars(query.order_by(VideoVersion.created_at.desc()))
        return [_video_version_dict(row) for row in rows]


@require_db
def point_ledger(user: dict[str, Any], page: int = 1, page_size: int = 10) -> dict[str, Any]:

    safe_page = max(1, page)
    safe_size = min(100, max(1, page_size))
    offset = (safe_page - 1) * safe_size
    with SessionLocal() as db:
        total = db.scalar(select(func.count(PointLedger.id)).where(PointLedger.user_id == user["id"]))
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
                    "created_at": fmt_dt(row.created_at),
                }
                for row in rows
            ],
            "total": total,
        }


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


@require_db
def _create_asset_common(
    db: Any,
    user_id: str,
    project_id: str,
    payload: Any,
    refs: list[dict],
    cost: int,
    ts: datetime,
    points_scene: str,
    points_desc: str,
    image_url: str | None,
    initial: str | None,
    voice_label: str | None,
    voice_url: str | None,
    voice_status: str | None,
) -> tuple[Asset, list[dict]] | dict[str, Any] | None:
    """Shared logic for create_asset and generate_asset."""
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user_id))
    target_user = db.get(User, user_id)
    if not project or not target_user:
        return None
    try:
        _change_points(db, user_id, -cost, "consume", points_scene, points_desc, ts)
    except ValueError as exc:
        return {"error": str(exc)}
    asset = Asset(
        id=uid("asset"),
        project_id=project_id,
        type=payload.type,
        name=payload.name,
        description=payload.description,
        initial=initial or payload.name[:1],
        image_url=image_url,
        voice_label=voice_label,
        voice_url=voice_url,
        voice_status=voice_status,
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
    visual_asset = payload.type in {"character", "scene", "image"}
    if visual_asset:
        usage = dict(target_user.usage_json or {})
        usage.setdefault("image_total", 1000)
        usage.setdefault("image_used", 0)
        usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)
        target_user.usage_json = usage
    project.updated_at = ts
    return asset, refs


@require_db
def create_asset(user: dict[str, Any], project_id: str, payload: Any, refs: list[dict], cost: int, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        result = _create_asset_common(
            db, user["id"], project_id, payload, refs, cost, ts,
            points_scene="创建素材",
            points_desc=f"创建素材《{payload.name}》",
            image_url=payload.image,
            initial=payload.initial[:1] if payload.initial else None,
            voice_label=payload.voice,
            voice_url=payload.voice_url,
            voice_status="uploaded" if payload.voice_url else None,
        )
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        asset, asset_refs = result
        db.commit()
        return _asset_dict(asset, asset_refs)


@require_db
def generate_asset(user: dict[str, Any], project_id: str, payload: Any, generated_url: str | None, refs: list[dict], cost: int, provider: str, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    visual_asset = payload.type in {"character", "scene", "image"}
    with SessionLocal() as db:
        result = _create_asset_common(
            db, user["id"], project_id, payload, refs, cost, ts,
            points_scene="AI 生成素材",
            points_desc=f"AI 生成素材《{payload.name}》",
            image_url=generated_url,
            initial=None,
            voice_label=None,
            voice_url=None,
            voice_status=None,
        )
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        asset, asset_refs = result
        _add_ai_job(db, user["id"], "image_asset" if visual_asset else "audio_asset", provider, cost, ts, project_id=project_id, asset_id=asset.id)
        db.commit()
        return _asset_dict(asset, asset_refs)


@require_db
def update_asset(user: dict[str, Any], asset_id: str, payload: Any, refs: list[dict] | None, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
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
        db.flush()
        ref_dicts = refs if refs is not None else [
            {"id": ref.id, "type": ref.type, "name": ref.name, "url": ref.url, "note": ref.note}
            for ref in db.scalars(select(AssetReference).where(AssetReference.asset_id == asset_id).order_by(AssetReference.sort_order))
        ]
        result = _asset_dict(asset, ref_dicts)
        db.commit()
        return result


@require_db
def delete_asset(user: dict[str, Any], asset_id: str) -> bool:
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


@require_db
def delete_video_version(user: dict[str, Any], version_id: str) -> bool:
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


@require_db
def get_asset(user: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
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


@require_db
def update_voice_clone(user: dict[str, Any], asset_id: str, result: dict[str, Any], cost: int, timestamp: str, consume: bool = True) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
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


@require_db
def save_composed_version(user: dict[str, Any], episode_id: str, payload: Any, video_url: str, cost: int, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
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
        version_no = db.scalar(select(func.count(VideoVersion.id)).where(VideoVersion.episode_id == episode_id)) + 1
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


@require_db
def usage(user: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        db_user = db.get(User, user["id"])
        usage_data = apply_usage_defaults(dict((db_user.usage_json if db_user else user.get("usage")) or {}))
        usage_data["team_members"] = db.scalar(select(func.count(User.id)).where(User.status == "active"))
        return usage_data


@require_db
def get_ai_job(user: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        job = db.get(AiJob, job_id)
        if not job:
            return None
        if job.user_id != user["id"] and user.get("role") != "admin":
            return {"error": "forbidden"}
        return _ai_job_dict(job)


@require_db
def list_project_ai_jobs(user: dict[str, Any], project_id: str) -> list[dict[str, Any]] | None:
    with SessionLocal() as db:
        owned = db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not owned:
            return None
        jobs = db.scalars(select(AiJob).where(AiJob.project_id == project_id).order_by(AiJob.created_at.desc()).limit(100))
        return [_ai_job_dict(job) for job in jobs]


@require_db
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
