"""Video database access. No HTTP exceptions here."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from ...db import SessionLocal, require_db
from ...models import AiJob, Asset, AssetReference, Episode, PointLedger, Project, Shot, User, VideoVersion
from ...serializers import _asset_dict, _episode_dict, _project_dict, _shot_dict, _video_job_dict, _video_version_dict
from ...utils import fmt_dt, parse_dt, uid


# Provider status → AiJob status mapping
_PROVIDER_STATUS_MAP = {
    "pending": "running",
    "running": "running",
    "generating": "running",
    "completed": "succeeded",
    "failed": "failed",
}


@require_db
def update_job_for_video_shot(job_id: str, shot_id: str, provider_task_id: str, timestamp: datetime) -> dict[str, Any] | None:
    """Update an existing AiJob (created by _run_paid_generation) with provider info and shot state."""
    ts = parse_dt(timestamp) if isinstance(timestamp, str) else timestamp
    with SessionLocal() as db:
        job = db.get(AiJob, job_id)
        if not job:
            return None
        shot = db.scalar(
            select(Shot)
            .join(Episode, Episode.id == Shot.episode_id)
            .join(Project, Project.id == Episode.project_id)
            .where(Shot.id == shot_id, Project.owner_user_id == job.user_id)
        )
        if not shot:
            return None
        job.provider_task_id = provider_task_id
        job.shot_id = shot.id
        job.episode_id = shot.episode_id
        episode = db.get(Episode, shot.episode_id)
        if episode:
            job.project_id = episode.project_id
        job.updated_at = ts
        shot.status = "generating"
        shot.updated_at = ts
        if episode:
            episode.updated_at = ts
            project = db.get(Project, episode.project_id)
            if project:
                project.updated_at = ts
        db.commit()
        return _video_job_dict(job, shot)


@require_db
def update_video_job_from_provider(job_id: str, remote: dict[str, Any]) -> None:
    """Update an AiJob (video_shot) from remote provider data.

    Maps provider statuses to AiJob statuses:
    - pending/running/generning → running
    - completed → succeeded
    - failed → failed
    """
    updated = {k: v for k, v in remote.items() if v is not None}
    ts = datetime.now()
    with SessionLocal() as db:
        job = db.get(AiJob, job_id)
        if not job:
            return

        # Update progress
        if "progress" in updated:
            job.progress = updated["progress"]

        # Update output URLs
        output = dict(job.output_json or {})
        if "preview_url" in updated:
            output["preview_url"] = updated["preview_url"]
        if "video_url" in updated:
            output["video_url"] = updated["video_url"]
        job.output_json = output

        # Map provider status to AiJob status
        provider_status = updated.get("status")
        if provider_status:
            new_job_status = _PROVIDER_STATUS_MAP.get(provider_status, job.status)
            previous_status = job.status
            job.status = new_job_status
            job.updated_at = ts

            # Terminal states
            if new_job_status in {"succeeded", "failed"}:
                job.completed_at = ts
                shot = db.get(Shot, job.shot_id)
                if shot:
                    # Shot uses provider-facing statuses: completed/failed
                    shot.status = "completed" if new_job_status == "succeeded" else "failed"
                    shot.updated_at = ts
                if new_job_status == "failed":
                    job.error = updated.get("error")
                    # Refund on failure
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
        else:
            job.updated_at = ts

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
        jobs = db.scalars(
            select(AiJob)
            .where(AiJob.episode_id == episode_id, AiJob.type == "video_shot", AiJob.status == "succeeded")
            .order_by(AiJob.created_at.desc())
        )
        # Keep only the latest succeeded job per shot
        seen_shots: set[str] = set()
        unique_jobs = []
        for j in jobs:
            if j.shot_id and j.shot_id not in seen_shots:
                seen_shots.add(j.shot_id)
                unique_jobs.append(j)
        shot_ids = {j.shot_id for j in unique_jobs}
        shots = {s.id: s for s in db.scalars(select(Shot).where(Shot.id.in_(shot_ids)))} if shot_ids else {}
        video_jobs = [_video_job_dict(j, shots.get(j.shot_id)) for j in unique_jobs]
    context["video_jobs"] = video_jobs
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
