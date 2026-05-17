from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ...db import SessionLocal, require_db
from ...models import AiJob, Asset, AssetReference, Episode, PointLedger, Project, Shot, User, VideoTask, VideoVersion
from ...serializers import _asset_dict, _episode_dict, _project_dict, _shot_dict, _video_task_dict, _video_version_dict
from ...utils import fmt_dt, parse_dt, uid


@require_db
def create_video_task(user: dict[str, Any], shot_id: str, provider_task_id: str, cost_per_second: int, timestamp: str) -> dict[str, Any] | None:
    from ..points.db import change_points
    from ..ai_job.db import add_ai_job

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
            change_points(db, user["id"], -cost, "consume", "生成镜头视频", f"生成镜头 #{shot.no}《{shot.title}》，{duration}s", ts)
        except ValueError as exc:
            return {"error": str(exc)}
        job = add_ai_job(
            db, user["id"], "video_shot", "seedance", cost, ts,
            status="running", progress=0, provider_task_id=provider_task_id,
            episode_id=shot.episode_id, shot_id=shot.id,
            project_id=episode.project_id if episode else None,
        )
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
def attach_video_task_to_job(user: dict[str, Any], shot_id: str, provider_task_id: str, job_id: str, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        shot = db.scalar(
            select(Shot)
            .join(Episode, Episode.id == Shot.episode_id)
            .join(Project, Project.id == Episode.project_id)
            .where(Shot.id == shot_id, Project.owner_user_id == user["id"])
        )
        job = db.scalar(select(AiJob).where(AiJob.id == job_id, AiJob.user_id == user["id"]))
        if not shot or not job:
            return None
        episode = db.get(Episode, shot.episode_id)
        duration = max(1, int(shot.duration))
        job.provider_task_id = provider_task_id
        job.episode_id = shot.episode_id
        job.shot_id = shot.id
        job.project_id = episode.project_id if episode else None
        job.updated_at = ts
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
    from ..points.db import change_points
    from ..ai_job.db import add_ai_job

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
                change_points(db, user["id"], -cost, "consume", "生成镜头视频", f"生成镜头 #{shot.no}《{shot.title}》，{duration}s", ts)
            except ValueError as exc:
                db.rollback()
                return [], str(exc)
            job = add_ai_job(
                db, user["id"], "video_shot", "seedance", cost, ts,
                status="running", progress=0, provider_task_id=provider_task_id,
                episode_id=shot.episode_id, shot_id=shot.id,
                project_id=episode.project_id if episode else None,
            )
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
    from ..points.db import change_points

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
                    previous_status = job.status
                    job.progress = task.get("progress", job.progress)
                    job.updated_at = ts
                    if task["status"] == "completed":
                        job.status = "succeeded"
                        job.completed_at = ts
                        job.output_json = {"video_url": task.get("video_url")}
                    else:
                        job.status = "failed"
                        job.error = task.get("error")
                        job.completed_at = ts
                        cost = int(job.cost_points or 0)
                        if previous_status not in {"failed", "cancelled"} and cost > 0:
                            user = db.execute(select(User).where(User.id == job.user_id).with_for_update()).scalar_one_or_none()
                            if user:
                                user.points = int(user.points or 0) + cost
                                db.add(
                                    PointLedger(
                                        id=uid("ledger"),
                                        user_id=job.user_id,
                                        amount=cost,
                                        type="refund",
                                        scene="生成失败退回",
                                        description="镜头视频生成失败退回积分",
                                        balance_after=user.points,
                                        ai_job_id=job.id,
                                        created_at=ts,
                                    )
                                )
        db.commit()


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
def compose_context(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    from ..storyboard.db import episode_generation_context

    context = episode_generation_context(user, episode_id)
    if not context:
        return None
    with SessionLocal() as db:
        tasks = [_video_task_dict(task) for task in db.scalars(select(VideoTask).where(VideoTask.episode_id == episode_id))]
    context["video_tasks"] = tasks
    return context


@require_db
def save_composed_version(user: dict[str, Any], episode_id: str, payload: Any, video_url: str, cost: int, timestamp: str, charge: bool = True, job_id: str | None = None) -> dict[str, Any] | None:
    from ..points.db import change_points
    from ..ai_job.db import add_ai_job

    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        episode = db.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            return None
        if charge:
            try:
                change_points(db, user["id"], -cost, "consume", "合成成片", f"合成《{episode.title}》成片版本", ts)
            except ValueError as exc:
                return {"error": str(exc)}
            add_ai_job(db, user["id"], "compose", "ffmpeg", cost, ts, episode_id=episode_id, project_id=episode.project_id)
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
        job = db.get(AiJob, job_id) if job_id else None
        if job:
            job.episode_id = episode_id
            job.project_id = episode.project_id
            job.status = "succeeded"
            job.progress = 100
            job.output_json = {"version_id": version.id, "video_url": video_url}
            job.updated_at = ts
            job.completed_at = ts
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
