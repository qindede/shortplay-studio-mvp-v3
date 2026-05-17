"""Unified storage adapter — delegates all persistence to db_store (PostgreSQL)."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from . import db_store
from .config import POINT_RULES
from .utils import now


def not_found(name: str):
    raise HTTPException(status_code=404, detail=f"{name} not found")


class Storage:
    """Thin facade over db_store with consistent error handling."""

    # ── READ ─────────────────────────────────────────────────────────────

    @staticmethod
    def dashboard(user: dict) -> dict:
        return db_store.dashboard(user)

    @staticmethod
    def workspace_bootstrap(user: dict) -> dict:
        return db_store.workspace_bootstrap(user)

    @staticmethod
    def list_projects(user: dict) -> list[dict]:
        return db_store.list_projects(user)

    @staticmethod
    def get_project(user: dict, project_id: str) -> dict:
        project = db_store.get_project(user, project_id)
        if not project:
            not_found("project")
        return project

    @staticmethod
    def list_episodes(user: dict, project_id: str) -> list[dict]:
        episodes = db_store.list_episodes(user, project_id)
        if episodes is None:
            not_found("project")
        return episodes

    @staticmethod
    def get_episode(user: dict, episode_id: str) -> dict:
        episode = db_store.get_episode(user, episode_id)
        if not episode:
            not_found("episode")
        return episode

    @staticmethod
    def episode_workspace(user: dict, episode_id: str) -> dict:
        payload = db_store.episode_workspace(user, episode_id)
        if payload is None:
            not_found("episode")
        return payload

    @staticmethod
    def list_shots(user: dict, episode_id: str) -> list[dict]:
        shots = db_store.list_shots(user, episode_id)
        if shots is None:
            not_found("episode")
        return shots

    @staticmethod
    def get_shot_with_context(user: dict, shot_id: str) -> tuple[dict, dict | None, list[dict]]:
        ctx = db_store.shot_generation_context(user, shot_id)
        if not ctx:
            not_found("shot")
        return ctx["shot"], ctx.get("episode"), ctx.get("assets", [])

    @staticmethod
    def list_assets(user: dict, project_id: str, asset_type: str | None = None) -> list[dict]:
        assets = db_store.list_assets(user, project_id, asset_type)
        if assets is None:
            not_found("project")
        return assets

    @staticmethod
    def get_asset(user: dict, asset_id: str) -> dict:
        asset = db_store.get_asset(user, asset_id)
        if not asset:
            not_found("asset")
        return asset

    @staticmethod
    def list_video_versions(user: dict, project_id: str, episode_id: str | None = None) -> list[dict]:
        versions = db_store.list_video_versions(user, project_id, episode_id)
        if versions is None:
            not_found("project")
        return versions

    @staticmethod
    def episode_generation_context(user: dict, episode_id: str) -> dict | None:
        return db_store.episode_generation_context(user, episode_id)

    @staticmethod
    def compose_context(user: dict, episode_id: str) -> dict | None:
        return db_store.compose_context(user, episode_id)

    @staticmethod
    def list_video_tasks_with_poll(user: dict, episode_id: str) -> list[dict]:
        payload = db_store.episode_workspace(user, episode_id)
        if payload is None:
            not_found("episode")
        tasks = payload["video_tasks"]
        for task in tasks:
            if task.get("status") != "generating" or not task.get("provider_task_id"):
                continue
            from .ai.video import query_video_task
            from .ai.errors import AIError
            try:
                remote = query_video_task(task["provider_task_id"])
            except AIError:
                continue
            db_store.update_video_task_from_provider(task, remote)
        return sorted(tasks, key=lambda t: t.get("updated_at", ""), reverse=True)

    @staticmethod
    def get_ai_job(user: dict, job_id: str) -> dict:
        job = db_store.get_ai_job(user, job_id)
        if not job:
            not_found("ai job")
        if job.get("error") == "forbidden":
            raise HTTPException(status_code=403, detail="无权访问该任务")
        return job

    @staticmethod
    def list_project_ai_jobs(user: dict, project_id: str) -> list[dict]:
        jobs = db_store.list_project_ai_jobs(user, project_id)
        if jobs is None:
            not_found("project")
        return jobs

    @staticmethod
    def usage(user: dict) -> dict:
        return db_store.usage(user)

    # ── CREATE ───────────────────────────────────────────────────────────

    @staticmethod
    def create_project(user: dict, payload: Any) -> dict:
        return db_store.create_project(user, payload, now())

    @staticmethod
    def create_episode(user: dict, project_id: str, payload: Any) -> dict:
        episode = db_store.create_episode(user, project_id, payload, now())
        if not episode:
            not_found("project")
        return episode

    @staticmethod
    def create_shot(user: dict, episode_id: str, payload: Any) -> dict:
        shot = db_store.create_shot(user, episode_id, payload, now())
        if shot is None:
            not_found("episode")
        return shot

    @staticmethod
    def create_asset(user: dict, project_id: str, payload: Any, refs: list[dict]) -> dict:
        visual_asset = payload.type in {"character", "scene", "image"}
        cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
        asset = db_store.create_asset(user, project_id, payload, refs, cost, now())
        if asset is None:
            not_found("project")
        if asset.get("error") == "insufficient_points":
            raise HTTPException(status_code=402, detail=f"积分不足：本次需要 {cost}")
        return asset

    # ── UPDATE ───────────────────────────────────────────────────────────

    @staticmethod
    def update_project(user: dict, project_id: str, payload: Any) -> dict:
        project = db_store.update_project(user, project_id, payload, now())
        if not project:
            not_found("project")
        return project

    @staticmethod
    def update_episode(user: dict, episode_id: str, payload: Any) -> dict:
        episode = db_store.update_episode(user, episode_id, payload, now())
        if not episode:
            not_found("episode")
        return episode

    @staticmethod
    def patch_shot(user: dict, shot_id: str, payload: Any) -> dict:
        shot = db_store.patch_shot(user, shot_id, payload, now())
        if not shot:
            not_found("shot")
        return shot

    @staticmethod
    def update_asset(user: dict, asset_id: str, payload: Any) -> dict:
        from .utils import normalize_refs
        refs_raw = payload.model_dump(exclude_unset=True).get("references")
        refs = normalize_refs(refs_raw) if refs_raw is not None else None
        asset = db_store.update_asset(user, asset_id, payload, refs, now())
        if not asset:
            not_found("asset")
        return asset

    @staticmethod
    def update_voice_clone(user: dict, asset_id: str, result: dict, cost: int = 0, consume: bool = True, create_job: bool = False) -> dict:
        updated = db_store.update_voice_clone(user, asset_id, result, now(), consume=consume)
        if updated is None:
            not_found("asset")
        if isinstance(updated, dict) and updated.get("error") == "insufficient_points":
            raise HTTPException(status_code=402, detail="积分不足")
        return updated

    # ── DELETE ───────────────────────────────────────────────────────────

    @staticmethod
    def delete_project(user: dict, project_id: str) -> dict:
        if not db_store.delete_project(user, project_id):
            not_found("project")
        return {"ok": True}

    @staticmethod
    def delete_episode(user: dict, episode_id: str) -> dict:
        ok, _project_id = db_store.delete_episode(user, episode_id, now())
        if not ok:
            not_found("episode")
        return {"ok": True}

    @staticmethod
    def delete_shot(user: dict, shot_id: str) -> dict:
        if not db_store.delete_shot(user, shot_id, now()):
            not_found("shot")
        return {"ok": True}

    @staticmethod
    def delete_asset(user: dict, asset_id: str) -> dict:
        if not db_store.delete_asset(user, asset_id):
            not_found("asset")
        return {"ok": True}

    @staticmethod
    def delete_video_version(user: dict, version_id: str) -> dict:
        if not db_store.delete_video_version(user, version_id):
            not_found("version")
        return {"ok": True}

    # ── COMPLEX WRITE ────────────────────────────────────────────────────

    @staticmethod
    def generate_project_outline(user: dict, episodes: list, cost: int, project_name: str) -> dict:
        result = db_store.consume_with_job(
            user["id"], cost, "生成短剧大纲",
            f"智能生成《{project_name}》短剧大纲", "outline", "minimax", now(),
        )
        if result.get("error") == "insufficient_points":
            raise HTTPException(status_code=402, detail=f"积分不足：本次需要 {cost}")
        return {"cost": cost, "episodes": episodes}

    @staticmethod
    def save_storyboard(user: dict, episode_id: str, ai_shots: list[dict], generated_assets: list[dict], storyboard_cost: int, asset_cost: int) -> list[dict]:
        result = db_store.save_storyboard(user, episode_id, ai_shots, generated_assets, storyboard_cost, asset_cost, now())
        if result is None:
            not_found("episode")
        if isinstance(result, dict) and result.get("error") == "insufficient_points":
            raise HTTPException(status_code=402, detail="积分不足")
        return result

    @staticmethod
    def generate_asset(user: dict, project_id: str, payload: Any, generated_url: str | None, refs: list[dict], visual_asset: bool) -> dict:
        cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
        provider = "seedream" if visual_asset else "manual"
        asset = db_store.generate_asset(user, project_id, payload, generated_url, refs, cost, provider, now())
        if asset is None:
            not_found("project")
        if asset.get("error") == "insufficient_points":
            raise HTTPException(status_code=402, detail=f"积分不足：本次需要 {cost}")
        return asset

    @staticmethod
    def create_video_task(user: dict, shot_id: str, provider_task_id: str, cost_per_second: int) -> dict:
        task = db_store.create_video_task(user, shot_id, provider_task_id, cost_per_second, now())
        if task is None:
            not_found("shot")
        if task.get("error") == "insufficient_points":
            raise HTTPException(status_code=402, detail="积分不足")
        return task

    @staticmethod
    def batch_create_video_tasks(user: dict, episode_id: str, provider_tasks: dict[str, str], cost_per_second: int) -> list[dict]:
        tasks, error = db_store.batch_create_video_tasks(user, provider_tasks, cost_per_second, now())
        if error == "insufficient_points":
            raise HTTPException(status_code=402, detail="积分不足")
        if error:
            raise HTTPException(status_code=400, detail=error)
        return tasks

    @staticmethod
    def save_composed_version(user: dict, episode_id: str, payload: Any, video_url: str, cost: int) -> dict:
        version = db_store.save_composed_version(user, episode_id, payload, video_url, cost, now())
        if isinstance(version, dict) and version.get("error") == "insufficient_points":
            raise HTTPException(status_code=402, detail="积分不足")
        return version

    # ── ADMIN ────────────────────────────────────────────────────────────

    @staticmethod
    def admin_summary() -> dict:
        return db_store.admin_summary()

    @staticmethod
    def admin_users() -> list[dict]:
        return db_store.admin_users()

    @staticmethod
    def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict:
        updated = db_store.admin_update_user(user_id, role, status)
        if not updated:
            not_found("user")
        return updated

    @staticmethod
    def admin_adjust_points(user_id: str, amount: int, reason: str) -> dict:
        result = db_store.admin_adjust_points(user_id, amount, reason, now())
        if result is None:
            not_found("user")
        return result

    @staticmethod
    def admin_reset_password(user_id: str, password_hash: str) -> dict:
        updated = db_store.admin_reset_password(user_id, password_hash)
        if not updated:
            not_found("user")
        return {"user": updated}

    @staticmethod
    def admin_point_ledger(user_id: str | None = None) -> list[dict]:
        return db_store.admin_point_ledger(user_id)

    # ── AUTH ─────────────────────────────────────────────────────────────

    @staticmethod
    def register_user(username: str, display_name: str, password_hash: str, token: str) -> dict | None:
        return db_store.register_user(username, display_name, password_hash, token, now())

    @staticmethod
    def login_user(username: str, password: str, token: str, last_login: str | None = None) -> dict | None:
        return db_store.login_user(username, password, token, last_login or now())

    @staticmethod
    def change_password(user_id: str, current_password: str, new_password: str) -> str:
        return db_store.change_password(user_id, current_password, new_password)

    @staticmethod
    def point_ledger(user: dict, page: int = 1, page_size: int = 10) -> dict:
        return db_store.point_ledger(user, page, page_size)

    @staticmethod
    def find_user_by_token(token: str | None) -> dict | None:
        return db_store.find_user_by_token(token)
