"""ORM-to-dict serialization functions for API responses."""
from __future__ import annotations

from typing import Any

from .config import STATUS_LABEL
from .models import (
    AiJob,
    Asset,
    Episode,
    PointLedger,
    Project,
    Shot,
    User,
    VideoVersion,
)
from .utils import fmt_dt


def _user_dict(row: User) -> dict[str, Any]:
    return {
        "id": row.id,
        "username": row.username,
        "display_name": row.display_name,
        "role": row.role,
        "status": row.status,
        "points": row.points,
        "usage": row.usage_json or {},
        "created_at": fmt_dt(row.created_at),
        "last_login": fmt_dt(row.last_login_at),
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
        "created_at": fmt_dt(row.created_at),
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
        "created_at": fmt_dt(row.created_at),
        "updated_at": fmt_dt(row.updated_at),
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
        "updated_at": fmt_dt(row.updated_at),
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
        "updated_at": fmt_dt(row.updated_at),
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
        "updated_at": fmt_dt(row.updated_at),
    }


_VIDEO_JOB_STATUS_MAP = {
    "pending": "pending",
    "running": "generating",
    "succeeded": "completed",
    "failed": "failed",
    "cancelled": "failed",
}


def _video_job_dict(job: AiJob, shot: Shot | None = None) -> dict[str, Any]:
    output = job.output_json or {}
    return {
        "id": job.id,
        "episode_id": job.episode_id,
        "shot_id": job.shot_id,
        "title": shot.title if shot else "",
        "duration": shot.duration if shot else 0,
        "progress": job.progress,
        "status": _VIDEO_JOB_STATUS_MAP.get(job.status, job.status),
        "provider": job.provider,
        "provider_task_id": job.provider_task_id,
        "preview_url": output.get("preview_url"),
        "video_url": output.get("video_url"),
        "error": job.error,
        "updated_at": fmt_dt(job.updated_at),
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
        "created_at": fmt_dt(row.created_at),
    }


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
        "created_at": fmt_dt(job.created_at),
        "updated_at": fmt_dt(job.updated_at),
        "completed_at": fmt_dt(job.completed_at),
    }
