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
    from .features.auth.queries import find_user_by_token as _find_user_by_token
    return _find_user_by_token(token)


@require_db
def find_user_by_username(username: str) -> dict[str, Any] | None:
    from .features.auth.queries import find_user_by_username as _find_user_by_username
    return _find_user_by_username(username)


@require_db
def get_public_user(user_id: str) -> dict[str, Any] | None:
    from .features.auth.queries import get_public_user as _get_public_user
    return _get_public_user(user_id)


@require_db
def user_has_points(user_id: str, cost: int) -> bool:
    from .features.points.queries import user_has_points as _user_has_points
    return _user_has_points(user_id, cost)


@require_db
def update_user_login(user_id: str, token: str, last_login: str) -> None:
    from .features.auth.queries import update_user_login as _update_user_login
    _update_user_login(user_id, token, last_login)


@require_db
def login_user(username: str, password: str, token: str, last_login: str) -> dict[str, Any] | None:
    from .features.auth.queries import login_user as _login_user
    return _login_user(username, password, token, last_login)


@require_db
def register_user(username: str, display_name: str, password_hash: str, token: str, timestamp: str, bonus_points: int = 1000) -> dict[str, Any] | None:
    from .features.auth.queries import register_user as _register_user
    return _register_user(username, display_name, password_hash, token, timestamp, bonus_points)


@require_db
def change_password(user_id: str, current_password: str, new_password: str) -> str:
    from .features.auth.queries import change_password as _change_password
    return _change_password(user_id, current_password, new_password)


@require_db
def admin_summary() -> dict[str, Any]:
    from .features.admin.queries import admin_summary as _admin_summary
    return _admin_summary()


@require_db
def admin_users() -> list[dict[str, Any]]:
    from .features.admin.queries import admin_users as _admin_users
    return _admin_users()


@require_db
def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict[str, Any] | None:
    from .features.admin.queries import admin_update_user as _admin_update_user
    return _admin_update_user(user_id, role, status)


@require_db
def admin_reset_password(user_id: str, password_hash: str) -> dict[str, Any] | None:
    from .features.admin.queries import admin_reset_password as _admin_reset_password
    return _admin_reset_password(user_id, password_hash)


@require_db
def admin_adjust_points(user_id: str, amount: int, reason: str, timestamp: str) -> dict[str, Any] | None:
    from .features.admin.queries import admin_adjust_points as _admin_adjust_points
    return _admin_adjust_points(user_id, amount, reason, timestamp)


@require_db
def admin_point_ledger(user_id: str | None = None) -> list[dict[str, Any]]:
    from .features.admin.queries import admin_point_ledger as _admin_point_ledger
    return _admin_point_ledger(user_id)



def _change_points(db, user_id: str, amount: int, kind: str, scene: str, description: str, timestamp: datetime | None) -> PointLedger:
    from .features.points.queries import change_points
    return change_points(db, user_id, amount, kind, scene, description, timestamp)


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
    from .features.ai_job.queries import add_ai_job
    return add_ai_job(db, user_id, job_type, provider, cost, timestamp, status=status, progress=progress, provider_task_id=provider_task_id, error=error, **links)


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
    from .features.ai_job.queries import consume_with_job as _consume_with_job
    return _consume_with_job(user_id, amount, ledger_scene, ledger_description, job_type, provider, timestamp, status=status, progress=progress, provider_task_id=provider_task_id, **links)


@require_db
def start_paid_ai_job(
    user_id: str,
    amount: int,
    ledger_scene: str,
    ledger_description: str,
    job_type: str,
    provider: str,
    timestamp: str,
    **links,
) -> dict[str, Any]:
    from .features.ai_job.queries import start_paid_ai_job as _start_paid_ai_job
    return _start_paid_ai_job(user_id, amount, ledger_scene, ledger_description, job_type, provider, timestamp, **links)


@require_db
def complete_ai_job(job_id: str, timestamp: str, output: dict[str, Any] | None = None) -> dict[str, Any] | None:
    from .features.ai_job.queries import complete_ai_job as _complete_ai_job
    return _complete_ai_job(job_id, timestamp, output)


@require_db
def fail_ai_job_with_refund(job_id: str, error: str, timestamp: str) -> dict[str, Any] | None:
    from .features.ai_job.queries import fail_ai_job_with_refund as _fail_ai_job_with_refund
    return _fail_ai_job_with_refund(job_id, error, timestamp)


@require_db
def episode_generation_context(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    from .features.storyboard.queries import episode_generation_context as _episode_generation_context
    return _episode_generation_context(user, episode_id)


@require_db
def save_storyboard(
    user: dict[str, Any],
    episode_id: str,
    ai_shots: list[dict],
    generated_assets: list[dict],
    storyboard_cost: int,
    asset_cost: int,
    timestamp: str,
    charge: bool = True,
) -> list[dict[str, Any]] | dict[str, str] | None:
    from .features.storyboard.queries import save_storyboard as _save_storyboard
    return _save_storyboard(user, episode_id, ai_shots, generated_assets, storyboard_cost, asset_cost, timestamp, charge)


@require_db
def shot_generation_context(user: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    from .features.shot.queries import shot_generation_context as _shot_generation_context
    return _shot_generation_context(user, shot_id)


@require_db
def create_video_task(user: dict[str, Any], shot_id: str, provider_task_id: str, cost_per_second: int, timestamp: str) -> dict[str, Any] | None:
    from .features.video.queries import create_video_task as _create_video_task
    return _create_video_task(user, shot_id, provider_task_id, cost_per_second, timestamp)


@require_db
def attach_video_task_to_job(user: dict[str, Any], shot_id: str, provider_task_id: str, job_id: str, timestamp: str) -> dict[str, Any] | None:
    from .features.video.queries import attach_video_task_to_job as _attach_video_task_to_job
    return _attach_video_task_to_job(user, shot_id, provider_task_id, job_id, timestamp)


@require_db
def batch_create_video_tasks(user: dict[str, Any], provider_tasks: dict[str, str], cost_per_second: int, timestamp: str) -> tuple[list[dict], str | None]:
    from .features.video.queries import batch_create_video_tasks as _batch_create_video_tasks
    return _batch_create_video_tasks(user, provider_tasks, cost_per_second, timestamp)


@require_db
def update_video_task_from_provider(task: dict[str, Any], remote: dict[str, Any]) -> None:
    from .features.video.queries import update_video_task_from_provider as _update_video_task_from_provider
    _update_video_task_from_provider(task, remote)


@require_db
def workspace_bootstrap(user: dict[str, Any]) -> dict[str, Any]:
    from .features.workspace.queries import workspace_bootstrap as _workspace_bootstrap
    return _workspace_bootstrap(user)


@require_db
def episode_workspace(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    from .features.workspace.queries import episode_workspace as _episode_workspace
    return _episode_workspace(user, episode_id)


@require_db
def create_shot(user: dict[str, Any], episode_id: str, payload: Any, shot_id: str, updated_at: str) -> dict[str, Any] | None:
    from .features.shot.queries import create_shot as _create_shot
    return _create_shot(user, episode_id, payload, shot_id, updated_at)


@require_db
def dashboard(user: dict[str, Any]) -> dict[str, Any]:
    from .features.workspace.queries import dashboard as _dashboard
    return _dashboard(user)


@require_db
def list_projects(user: dict[str, Any]) -> list[dict[str, Any]]:
    from .features.project.queries import list_projects as _list_projects
    return _list_projects(user)


@require_db
def list_episodes(user: dict[str, Any], project_id: str) -> list[dict[str, Any]] | None:
    from .features.episode.queries import list_episodes as _list_episodes
    return _list_episodes(user, project_id)


@require_db
def list_shots(user: dict[str, Any], episode_id: str) -> list[dict[str, Any]] | None:
    from .features.shot.queries import list_shots as _list_shots
    return _list_shots(user, episode_id)


@require_db
def list_assets(user: dict[str, Any], project_id: str, asset_type: str | None = None) -> list[dict[str, Any]] | None:
    from .features.asset.queries import list_assets as _list_assets
    return _list_assets(user, project_id, asset_type)


@require_db
def list_video_versions(user: dict[str, Any], project_id: str, episode_id: str | None = None) -> list[dict[str, Any]] | None:
    from .features.video.queries import list_video_versions as _list_video_versions
    return _list_video_versions(user, project_id, episode_id)


@require_db
def point_ledger(user: dict[str, Any], page: int = 1, page_size: int = 10) -> dict[str, Any]:
    from .features.points.queries import point_ledger as _point_ledger
    return _point_ledger(user, page, page_size)


@require_db
def get_project(user: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    from .features.project.queries import get_project as _get_project
    return _get_project(user, project_id)


@require_db
def create_project(user: dict[str, Any], payload: Any, timestamp: str) -> dict[str, Any]:
    from .features.project.queries import create_project as _create_project
    return _create_project(user, payload, timestamp)


@require_db
def update_project(user: dict[str, Any], project_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    from .features.project.queries import update_project as _update_project
    return _update_project(user, project_id, payload, timestamp)


@require_db
def delete_project(user: dict[str, Any], project_id: str) -> bool:
    from .features.project.queries import delete_project as _delete_project
    return _delete_project(user, project_id)


@require_db
def get_episode(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    from .features.episode.queries import get_episode as _get_episode
    return _get_episode(user, episode_id)


@require_db
def create_episode(user: dict[str, Any], project_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    from .features.episode.queries import create_episode as _create_episode
    return _create_episode(user, project_id, payload, timestamp)


@require_db
def update_episode(user: dict[str, Any], episode_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    from .features.episode.queries import update_episode as _update_episode
    return _update_episode(user, episode_id, payload, timestamp)


@require_db
def delete_episode(user: dict[str, Any], episode_id: str, timestamp: str) -> tuple[bool, str | None]:
    from .features.episode.queries import delete_episode as _delete_episode
    return _delete_episode(user, episode_id, timestamp)


@require_db
def patch_shot(user: dict[str, Any], shot_id: str, payload: Any, timestamp: str) -> dict[str, Any] | None:
    from .features.shot.queries import patch_shot as _patch_shot
    return _patch_shot(user, shot_id, payload, timestamp)


@require_db
def delete_shot(user: dict[str, Any], shot_id: str, timestamp: str) -> bool:
    from .features.shot.queries import delete_shot as _delete_shot
    return _delete_shot(user, shot_id, timestamp)


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
    from .features.asset.queries import _create_asset_common as __create_asset_common
    return __create_asset_common(db, user_id, project_id, payload, refs, cost, ts, points_scene, points_desc, image_url, initial, voice_label, voice_url, voice_status)


@require_db
def create_asset(user: dict[str, Any], project_id: str, payload: Any, refs: list[dict], cost: int, timestamp: str) -> dict[str, Any] | None:
    from .features.asset.queries import create_asset as _create_asset
    return _create_asset(user, project_id, payload, refs, cost, timestamp)


@require_db
def generate_asset(user: dict[str, Any], project_id: str, payload: Any, generated_url: str | None, refs: list[dict], cost: int, provider: str, timestamp: str) -> dict[str, Any] | None:
    from .features.asset.queries import generate_asset as _generate_asset
    return _generate_asset(user, project_id, payload, generated_url, refs, cost, provider, timestamp)


@require_db
def generate_asset_without_charge(user: dict[str, Any], project_id: str, payload: Any, generated_url: str | None, refs: list[dict], timestamp: str) -> dict[str, Any] | None:
    from .features.asset.queries import generate_asset_without_charge as _generate_asset_without_charge
    return _generate_asset_without_charge(user, project_id, payload, generated_url, refs, timestamp)


@require_db
def update_asset(user: dict[str, Any], asset_id: str, payload: Any, refs: list[dict] | None, timestamp: str) -> dict[str, Any] | None:
    from .features.asset.queries import update_asset as _update_asset
    return _update_asset(user, asset_id, payload, refs, timestamp)


@require_db
def delete_asset(user: dict[str, Any], asset_id: str) -> bool:
    from .features.asset.queries import delete_asset as _delete_asset
    return _delete_asset(user, asset_id)


@require_db
def delete_video_version(user: dict[str, Any], version_id: str) -> bool:
    from .features.video.queries import delete_video_version as _delete_video_version
    return _delete_video_version(user, version_id)


@require_db
def get_asset(user: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    from .features.asset.queries import get_asset as _get_asset
    return _get_asset(user, asset_id)


@require_db
def update_voice_clone(user: dict[str, Any], asset_id: str, result: dict[str, Any], cost: int, timestamp: str, consume: bool = True, job_id: str | None = None) -> dict[str, Any] | None:
    from .features.asset.queries import update_voice_clone as _update_voice_clone
    return _update_voice_clone(user, asset_id, result, cost, timestamp, consume, job_id)


def compose_context(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:
    from .features.video.queries import compose_context as _compose_context
    return _compose_context(user, episode_id)


@require_db
def save_composed_version(user: dict[str, Any], episode_id: str, payload: Any, video_url: str, cost: int, timestamp: str, charge: bool = True, job_id: str | None = None) -> dict[str, Any] | None:
    from .features.video.queries import save_composed_version as _save_composed_version
    return _save_composed_version(user, episode_id, payload, video_url, cost, timestamp, charge, job_id)


@require_db
def usage(user: dict[str, Any]) -> dict[str, Any]:
    from .features.points.queries import usage as _usage
    return _usage(user)


@require_db
def get_ai_job(user: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    from .features.ai_job.queries import get_ai_job as _get_ai_job
    return _get_ai_job(user, job_id)


@require_db
def list_project_ai_jobs(user: dict[str, Any], project_id: str) -> list[dict[str, Any]] | None:
    from .features.ai_job.queries import list_project_ai_jobs as _list_project_ai_jobs
    return _list_project_ai_jobs(user, project_id)


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
