"""Unified storage adapter — eliminates if db_store.enabled() branching in routers."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from . import db_store
from .config import POINT_RULES
from .security import public_user
from .services import (
    change_points,
    comparable_asset_names,
    enrich_episode,
    enrich_project,
    find_by_id,
    get_user_projects,
    get_user_usage,
    normalize_refs,
    not_found,
    renumber,
    touch_episode_and_project,
    touch_project,
    usage_with_members,
    verify_project_ownership,
)
from .store import now, snapshot, uid, update


class Storage:
    """Thin facade that routes to db_store or JSON store transparently."""

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _ts(timestamp: str | None = None) -> str:
        return timestamp or now()

    # ── READ ─────────────────────────────────────────────────────────────

    @staticmethod
    def dashboard(user: dict) -> dict:
        if db_store.enabled():
            return db_store.dashboard(user)
        data = snapshot()
        user_projects = get_user_projects(data, user["id"])
        project_ids = {p["id"] for p in user_projects}
        return {
            "project_count": len(user_projects),
            "episode_count": len([e for e in data["episodes"] if e["project_id"] in project_ids]),
            "version_count": len([v for v in data["video_versions"] if v["project_id"] in project_ids]),
            "asset_count": len([a for a in data["assets"] if a["project_id"] in project_ids]),
            "usage": usage_with_members(data, user["id"]),
            "current_user": user,
        }

    @staticmethod
    def workspace_bootstrap(user: dict) -> dict:
        if db_store.enabled():
            return db_store.workspace_bootstrap(user)
        data = snapshot()
        user_projects = get_user_projects(data, user["id"])
        project_ids = {p["id"] for p in user_projects}
        dashboard_data = {
            "project_count": len(user_projects),
            "episode_count": len([e for e in data["episodes"] if e["project_id"] in project_ids]),
            "version_count": len([v for v in data["video_versions"] if v["project_id"] in project_ids]),
            "asset_count": len([a for a in data["assets"] if a["project_id"] in project_ids]),
            "usage": usage_with_members(data, user["id"]),
            "current_user": user,
        }
        ledger_rows = [e for e in data.get("point_ledger", []) if e["user_id"] == user["id"]]
        projects = [enrich_project(data, p) for p in user_projects]

        current_project = projects[0] if projects else None
        project_episodes: list[dict] = []
        project_assets: list[dict] = []
        selected_episode = None
        episode_shots: list[dict] = []
        episode_tasks: list[dict] = []
        project_versions: list[dict] = []

        if current_project:
            project_episodes = [e for e in data["episodes"] if e["project_id"] == current_project["id"]]
            project_episodes.sort(key=lambda x: x["no"])
            project_episodes = [enrich_episode(data, e) for e in project_episodes]
            project_assets = [a for a in data["assets"] if a["project_id"] == current_project["id"]]

            if project_episodes:
                selected_episode = project_episodes[0]
                episode_shots = [s for s in data["shots"] if s["episode_id"] == selected_episode["id"]]
                episode_shots.sort(key=lambda x: x["no"])
                episode_tasks = [t for t in data["video_tasks"] if t["episode_id"] == selected_episode["id"]]
                episode_tasks.sort(key=lambda x: x["updated_at"], reverse=True)
                project_versions = [
                    v for v in data["video_versions"]
                    if v["project_id"] == current_project["id"] and v["episode_id"] == selected_episode["id"]
                ]
            else:
                project_versions = [v for v in data["video_versions"] if v["project_id"] == current_project["id"]]
            project_versions.sort(key=lambda x: x["created_at"], reverse=True)

        return {
            "dashboard": dashboard_data,
            "point_ledger": {"items": ledger_rows[:10], "total": len(ledger_rows)},
            "projects": projects,
            "current_project": current_project,
            "episodes": project_episodes,
            "selected_episode": selected_episode,
            "shots": episode_shots,
            "assets": project_assets,
            "video_tasks": episode_tasks,
            "versions": project_versions,
        }

    @staticmethod
    def list_projects(user: dict) -> list[dict]:
        if db_store.enabled():
            return db_store.list_projects(user)
        data = snapshot()
        return [enrich_project(data, p) for p in get_user_projects(data, user["id"])]

    @staticmethod
    def get_project(user: dict, project_id: str) -> dict:
        if db_store.enabled():
            project = db_store.get_project(user, project_id)
            if not project:
                not_found("project")
            return project
        data = snapshot()
        return enrich_project(data, verify_project_ownership(data, project_id, user["id"]))

    @staticmethod
    def list_episodes(user: dict, project_id: str) -> list[dict]:
        if db_store.enabled():
            episodes = db_store.list_episodes(user, project_id)
            if episodes is None:
                not_found("project")
            return episodes
        data = snapshot()
        verify_project_ownership(data, project_id, user["id"])
        episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
        episodes.sort(key=lambda x: x["no"])
        return [enrich_episode(data, e) for e in episodes]

    @staticmethod
    def get_episode(user: dict, episode_id: str) -> dict:
        if db_store.enabled():
            episode = db_store.get_episode(user, episode_id)
            if not episode:
                not_found("episode")
            return episode
        data = snapshot()
        episode = find_by_id(data["episodes"], episode_id, "episode")
        verify_project_ownership(data, episode["project_id"], user["id"])
        return enrich_episode(data, episode)

    @staticmethod
    def episode_workspace(user: dict, episode_id: str) -> dict:
        if db_store.enabled():
            payload = db_store.episode_workspace(user, episode_id)
            if payload is None:
                not_found("episode")
            return payload
        data = snapshot()
        episode = find_by_id(data["episodes"], episode_id, "episode")
        verify_project_ownership(data, episode["project_id"], user["id"])
        shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        shots.sort(key=lambda x: x["no"])
        tasks = [t for t in data["video_tasks"] if t["episode_id"] == episode_id]
        tasks.sort(key=lambda x: x["updated_at"], reverse=True)
        versions = [v for v in data["video_versions"] if v["project_id"] == episode["project_id"] and v["episode_id"] == episode_id]
        versions.sort(key=lambda x: x["created_at"], reverse=True)
        return {"shots": shots, "video_tasks": tasks, "versions": versions}

    @staticmethod
    def list_shots(user: dict, episode_id: str) -> list[dict]:
        if db_store.enabled():
            shots = db_store.list_shots(user, episode_id)
            if shots is None:
                not_found("episode")
            return shots
        data = snapshot()
        episode = find_by_id(data["episodes"], episode_id, "episode")
        verify_project_ownership(data, episode["project_id"], user["id"])
        shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        shots.sort(key=lambda x: x["no"])
        return shots

    @staticmethod
    def get_shot_with_context(user: dict, shot_id: str) -> tuple[dict, dict | None, list[dict]]:
        """Returns (shot, episode_or_None, assets)."""
        if db_store.enabled():
            ctx = db_store.shot_generation_context(user, shot_id)
            if not ctx:
                not_found("shot")
            return ctx["shot"], ctx.get("episode"), ctx.get("assets", [])
        data = snapshot()
        shot = find_by_id(data["shots"], shot_id, "shot")
        episode = next((e for e in data["episodes"] if e["id"] == shot["episode_id"]), None)
        if episode:
            verify_project_ownership(data, episode["project_id"], user["id"])
        assets = [a for a in data["assets"] if episode and a["project_id"] == episode["project_id"]]
        return shot, episode, assets

    @staticmethod
    def list_assets(user: dict, project_id: str, asset_type: str | None = None) -> list[dict]:
        if db_store.enabled():
            assets = db_store.list_assets(user, project_id, asset_type)
            if assets is None:
                not_found("project")
            return assets
        data = snapshot()
        verify_project_ownership(data, project_id, user["id"])
        assets = [a for a in data["assets"] if a["project_id"] == project_id]
        if asset_type:
            assets = [a for a in assets if a["type"] == asset_type]
        return assets

    @staticmethod
    def get_asset(user: dict, asset_id: str) -> dict:
        if db_store.enabled():
            asset = db_store.get_asset(user, asset_id)
            if not asset:
                not_found("asset")
            return asset
        data = snapshot()
        asset = find_by_id(data["assets"], asset_id, "asset")
        verify_project_ownership(data, asset["project_id"], user["id"])
        return asset

    @staticmethod
    def list_video_versions(user: dict, project_id: str, episode_id: str | None = None) -> list[dict]:
        if db_store.enabled():
            versions = db_store.list_video_versions(user, project_id, episode_id)
            if versions is None:
                not_found("project")
            return versions
        data = snapshot()
        verify_project_ownership(data, project_id, user["id"])
        versions = [v for v in data["video_versions"] if v["project_id"] == project_id]
        if episode_id:
            versions = [v for v in versions if v["episode_id"] == episode_id]
        versions.sort(key=lambda x: x["created_at"], reverse=True)
        return versions

    @staticmethod
    def episode_generation_context(user: dict, episode_id: str) -> dict | None:
        if db_store.enabled():
            return db_store.episode_generation_context(user, episode_id)
        data = snapshot()
        episode = find_by_id(data["episodes"], episode_id, "episode")
        project = verify_project_ownership(data, episode["project_id"], user["id"])
        assets = [a for a in data["assets"] if a["project_id"] == project["id"]]
        shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        shots.sort(key=lambda x: x["no"])
        return {
            "project": enrich_project(data, project),
            "episode": enrich_episode(data, episode),
            "assets": assets,
            "shots": shots,
        }

    @staticmethod
    def compose_context(user: dict, episode_id: str) -> dict | None:
        if db_store.enabled():
            return db_store.compose_context(user, episode_id)
        data = snapshot()
        episode = find_by_id(data["episodes"], episode_id, "episode")
        project = verify_project_ownership(data, episode["project_id"], user["id"])
        assets = [a for a in data["assets"] if a["project_id"] == project["id"]]
        shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        shots.sort(key=lambda x: x["no"])
        tasks = [t for t in data["video_tasks"] if t["episode_id"] == episode_id]
        return {
            "project": enrich_project(data, project),
            "episode": enrich_episode(data, episode),
            "assets": assets,
            "shots": shots,
            "video_tasks": tasks,
        }

    @staticmethod
    def list_video_tasks_with_poll(user: dict, episode_id: str) -> list[dict]:
        if db_store.enabled():
            payload = db_store.episode_workspace(user, episode_id)
            if payload is None:
                not_found("episode")
            return payload["video_tasks"]

        from .ai.video import query_video_task
        from .ai.errors import AIError

        def mutate(data):
            episode = find_by_id(data["episodes"], episode_id, "episode")
            verify_project_ownership(data, episode["project_id"], user["id"])
            tasks = [t for t in data["video_tasks"] if t["episode_id"] == episode_id]
            for task in tasks:
                if task.get("status") != "generating" or not task.get("provider_task_id"):
                    continue
                try:
                    remote = query_video_task(task["provider_task_id"])
                except AIError:
                    continue
                task.update({key: value for key, value in remote.items() if value is not None})
                task["updated_at"] = now()
                job = next((item for item in data.get("ai_jobs", []) if item.get("id") == task.get("ai_job_id")), None)
                if job:
                    job["progress"] = task.get("progress", job.get("progress", 0))
                    job["updated_at"] = task["updated_at"]
                    if task.get("status") == "completed":
                        job["status"] = "succeeded"
                        job["completed_at"] = task["updated_at"]
                        job["output_json"] = {"video_url": task.get("video_url")}
                    elif task.get("status") == "failed":
                        job["status"] = "failed"
                        job["error"] = task.get("error")
                        job["completed_at"] = task["updated_at"]
                shot = next((s for s in data["shots"] if s["id"] == task["shot_id"]), None)
                if shot and task.get("status") in {"completed", "failed"}:
                    shot["status"] = task["status"]
                    shot["updated_at"] = task["updated_at"]
                if task.get("status") == "failed":
                    refund_target = job or task
                    from .services import refund_once
                    refund_once(data, user["id"], refund_target, task["duration"] * POINT_RULES["video_second"], "视频生成失败退款", task.get("error") or "视频任务失败")
            tasks.sort(key=lambda x: x["updated_at"], reverse=True)
            return tasks

        return update(mutate)

    @staticmethod
    def get_ai_job(user: dict, job_id: str) -> dict:
        if db_store.enabled():
            job = db_store.get_ai_job(user, job_id)
            if not job:
                not_found("ai job")
            if job.get("error") == "forbidden":
                raise HTTPException(status_code=403, detail="无权访问该任务")
            return job
        data = snapshot()
        job = find_by_id(data.get("ai_jobs", []), job_id, "ai job")
        if job.get("user_id") != user["id"] and user.get("role") != "admin":

            raise HTTPException(status_code=403, detail="无权访问该任务")
        return job

    @staticmethod
    def list_project_ai_jobs(user: dict, project_id: str) -> list[dict]:
        if db_store.enabled():
            jobs = db_store.list_project_ai_jobs(user, project_id)
            if jobs is None:
                not_found("project")
            return jobs
        data = snapshot()
        verify_project_ownership(data, project_id, user["id"])
        return [job for job in data.get("ai_jobs", []) if job.get("project_id") == project_id][:100]

    @staticmethod
    def usage(user: dict) -> dict:
        if db_store.enabled():
            return db_store.usage(user)
        data = snapshot()
        return usage_with_members(data, user["id"])

    # ── CREATE ───────────────────────────────────────────────────────────

    @staticmethod
    def create_project(user: dict, payload: Any) -> dict:
        if db_store.enabled():
            return db_store.create_project(user, payload, now())

        def mutate(data):
            ts = now()
            project = {
                "id": uid("proj"),
                "name": payload.name.strip(),
                "short_name": payload.name.strip()[:8],
                "description": payload.description,
                "status": "draft",
                "owner": payload.owner if payload.owner and payload.owner != "未分配" else user["display_name"],
                "owner_user_id": user["id"],
                "cover": "dark",
                "updated_at": ts,
            }
            data["projects"].insert(0, project)
            for index, item in enumerate(payload.episodes, start=1):
                data["episodes"].append({
                    "id": uid("ep"),
                    "project_id": project["id"],
                    "no": index,
                    "title": item.title,
                    "summary": item.summary,
                    "script": item.script or item.summary,
                    "duration_target": item.duration_target,
                    "status": "draft",
                    "updated_at": ts,
                })
            return enrich_project(data, project)

        return update(mutate)

    @staticmethod
    def create_episode(user: dict, project_id: str, payload: Any) -> dict:
        if db_store.enabled():
            episode = db_store.create_episode(user, project_id, payload, now())
            if not episode:
                not_found("project")
            return episode

        def mutate(data):
            verify_project_ownership(data, project_id, user["id"])
            project_episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
            ts = now()
            episode = {
                "id": uid("ep"),
                "project_id": project_id,
                "no": max([e["no"] for e in project_episodes] or [0]) + 1,
                "title": payload.title,
                "summary": payload.summary,
                "script": payload.script or payload.summary,
                "duration_target": payload.duration_target,
                "status": "draft",
                "updated_at": ts,
            }
            data["episodes"].append(episode)
            touch_project(data, project_id, ts)
            return enrich_episode(data, episode)

        return update(mutate)

    @staticmethod
    def create_shot(user: dict, episode_id: str, payload: Any) -> dict:
        if db_store.enabled():
            shot = db_store.create_shot(user, episode_id, payload, uid("shot"), now())
            if shot is None:
                not_found("episode")
            return shot

        def mutate(data):
            episode = find_by_id(data["episodes"], episode_id, "episode")
            verify_project_ownership(data, episode["project_id"], user["id"])
            episode_shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
            ts = now()
            shot = {
                "id": uid("shot"),
                "episode_id": episode_id,
                "no": max([s["no"] for s in episode_shots], default=0) + 1,
                "title": payload.title,
                "visual": payload.visual,
                "dialogue": payload.dialogue,
                "characters": payload.characters,
                "scene": payload.scene,
                "duration": payload.duration,
                "status": "pending",
                "updated_at": ts,
            }
            data["shots"].append(shot)
            episode["status"] = "storyboard_ready"
            touch_episode_and_project(data, episode, ts)
            return shot

        return update(mutate)

    @staticmethod
    def create_asset(user: dict, project_id: str, payload: Any, refs: list[dict]) -> dict:


        if db_store.enabled():
            visual_asset = payload.type in {"character", "scene", "image"}
            cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
            asset = db_store.create_asset(user, project_id, payload, refs, cost, now())
            if asset is None:
                not_found("project")
            if asset.get("error") == "points":
                raise HTTPException(status_code=402, detail=f"积分不足：本次需要 {cost}")
            return asset

        def mutate(data):
            verify_project_ownership(data, project_id, user["id"])
            visual_asset = payload.type in {"character", "scene", "image"}
            cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
            change_points(data, user["id"], -cost, "consume", "创建素材", f"创建素材《{payload.name}》")
            ts = now()
            asset = {
                "id": uid("asset"),
                "project_id": project_id,
                "type": payload.type,
                "name": payload.name,
                "description": payload.description,
                "ref_count": len(refs),
                "initial": payload.initial[:1] or payload.name[:1],
                "image": payload.image,
                "voice": payload.voice,
                "voice_url": payload.voice_url,
                "voice_status": "uploaded" if payload.voice_url else None,
                "references": refs,
                "updated_at": ts,
            }
            data["assets"].insert(0, asset)
            if visual_asset:
                usage = get_user_usage(data, user["id"])
                usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)
            touch_project(data, project_id, ts)
            return asset

        return update(mutate)

    # ── UPDATE ───────────────────────────────────────────────────────────

    @staticmethod
    def update_project(user: dict, project_id: str, payload: Any) -> dict:
        if db_store.enabled():
            project = db_store.update_project(user, project_id, payload, now())
            if not project:
                not_found("project")
            return project

        def mutate(data):
            project = verify_project_ownership(data, project_id, user["id"])
            updates = payload.model_dump(exclude_none=True)
            if "name" in updates:
                project["name"] = updates["name"].strip()
                project["short_name"] = project["name"][:8]
            if "description" in updates:
                project["description"] = updates["description"]
            if "status" in updates:
                project["status"] = updates["status"]
            touch_project(data, project_id)
            return enrich_project(data, project)

        return update(mutate)

    @staticmethod
    def update_episode(user: dict, episode_id: str, payload: Any) -> dict:
        if db_store.enabled():
            episode = db_store.update_episode(user, episode_id, payload, now())
            if not episode:
                not_found("episode")
            return episode

        def mutate(data):
            episode = find_by_id(data["episodes"], episode_id, "episode")
            verify_project_ownership(data, episode["project_id"], user["id"])
            episode.update(payload.model_dump(exclude_none=True))
            touch_episode_and_project(data, episode)
            return enrich_episode(data, episode)

        return update(mutate)

    @staticmethod
    def patch_shot(user: dict, shot_id: str, payload: Any) -> dict:
        if db_store.enabled():
            shot = db_store.patch_shot(user, shot_id, payload, now())
            if not shot:
                not_found("shot")
            return shot

        def mutate(data):
            shot = find_by_id(data["shots"], shot_id, "shot")
            episode = next((e for e in data["episodes"] if e["id"] == shot["episode_id"]), None)
            if episode:
                verify_project_ownership(data, episode["project_id"], user["id"])
            updates = payload.model_dump(exclude_none=True)
            shot.update(updates)
            shot["updated_at"] = now()
            task = next((t for t in data["video_tasks"] if t["shot_id"] == shot_id), None)
            if task:
                if "title" in updates:
                    task["title"] = shot["title"]
                if "duration" in updates:
                    task["duration"] = shot["duration"]
                task["updated_at"] = now()
            if episode:
                touch_episode_and_project(data, episode)
            return shot

        return update(mutate)

    @staticmethod
    def update_asset(user: dict, asset_id: str, payload: Any) -> dict:
        refs_raw = payload.model_dump(exclude_unset=True).get("references")
        refs = normalize_refs(refs_raw) if refs_raw is not None else None

        if db_store.enabled():
            asset = db_store.update_asset(user, asset_id, payload, refs, now())
            if not asset:
                not_found("asset")
            return asset

        def mutate(data):
            asset = find_by_id(data["assets"], asset_id, "asset")
            verify_project_ownership(data, asset["project_id"], user["id"])
            update_data = payload.model_dump(exclude_unset=True)
            if refs is not None:
                update_data["references"] = refs
                update_data["ref_count"] = len(refs)
            asset.update(update_data)
            asset["updated_at"] = now()
            touch_project(data, asset["project_id"], asset["updated_at"])
            return asset

        return update(mutate)

    @staticmethod
    def update_voice_clone(user: dict, asset_id: str, result: dict, cost: int = 0, consume: bool = True, create_job: bool = False) -> dict:
        if db_store.enabled():
            updated = db_store.update_voice_clone(user, asset_id, result, cost, now(), consume=consume)
            if updated is None:
                not_found("asset")
            if isinstance(updated, dict) and updated.get("error") == "insufficient_points":
                raise HTTPException(status_code=402, detail="积分不足")
            return updated

        def mutate(data):
            target = find_by_id(data["assets"], asset_id, "asset")
            verify_project_ownership(data, target["project_id"], user["id"])
            if consume and cost > 0:
                change_points(data, user["id"], -cost, "consume", "音色克隆", f"训练《{target['name']}》角色音色")
            target.update({k: v for k, v in result.items() if v is not None})
            target["updated_at"] = now()
            if create_job:
                from .services import add_ai_job
                job = add_ai_job(
                    data, user["id"], "voice_clone", "volc_voice", cost or 0,
                    status="succeeded" if target.get("voice_status") == "completed" else "running",
                    progress=100 if target.get("voice_status") == "completed" else 0,
                    provider_task_id=target.get("speaker_id"),
                    project_id=target["project_id"], asset_id=asset_id,
                )
                if job["status"] == "running":
                    job["completed_at"] = ""
            return target

        return update(mutate)

    # ── DELETE ───────────────────────────────────────────────────────────

    @staticmethod
    def delete_project(user: dict, project_id: str) -> dict:
        if db_store.enabled():
            if not db_store.delete_project(user, project_id):
                not_found("project")
            return {"ok": True}

        def mutate(data):
            verify_project_ownership(data, project_id, user["id"])
            episode_ids = {e["id"] for e in data["episodes"] if e["project_id"] == project_id}
            shot_ids = {s["id"] for s in data["shots"] if s["episode_id"] in episode_ids}
            data["projects"] = [p for p in data["projects"] if p["id"] != project_id]
            data["episodes"] = [e for e in data["episodes"] if e["project_id"] != project_id]
            data["shots"] = [s for s in data["shots"] if s["episode_id"] not in episode_ids]
            data["assets"] = [a for a in data["assets"] if a["project_id"] != project_id]
            data["video_tasks"] = [t for t in data["video_tasks"] if t.get("episode_id") not in episode_ids and t.get("shot_id") not in shot_ids]
            data["video_versions"] = [v for v in data["video_versions"] if v["project_id"] != project_id]
            return {"ok": True}

        return update(mutate)

    @staticmethod
    def delete_episode(user: dict, episode_id: str) -> dict:
        if db_store.enabled():
            ok, _project_id = db_store.delete_episode(user, episode_id, now())
            if not ok:
                not_found("episode")
            return {"ok": True}

        def mutate(data):
            episode = find_by_id(data["episodes"], episode_id, "episode")
            verify_project_ownership(data, episode["project_id"], user["id"])
            project_id = episode["project_id"]
            data["episodes"] = [e for e in data["episodes"] if e["id"] != episode_id]
            data["shots"] = [s for s in data["shots"] if s["episode_id"] != episode_id]
            data["video_tasks"] = [t for t in data["video_tasks"] if t["episode_id"] != episode_id]
            data["video_versions"] = [v for v in data["video_versions"] if v["episode_id"] != episode_id]
            renumber([e for e in data["episodes"] if e["project_id"] == project_id])
            touch_project(data, project_id)
            return {"ok": True}

        return update(mutate)

    @staticmethod
    def delete_shot(user: dict, shot_id: str) -> dict:
        if db_store.enabled():
            if not db_store.delete_shot(user, shot_id, now()):
                not_found("shot")
            return {"ok": True}

        def mutate(data):
            shot = find_by_id(data["shots"], shot_id, "shot")
            episode = next((e for e in data["episodes"] if e["id"] == shot["episode_id"]), None)
            if episode:
                verify_project_ownership(data, episode["project_id"], user["id"])
            data["shots"] = [s for s in data["shots"] if s["id"] != shot_id]
            data["video_tasks"] = [t for t in data["video_tasks"] if t["shot_id"] != shot_id]
            renumber([s for s in data["shots"] if s["episode_id"] == shot["episode_id"]])
            if episode:
                touch_episode_and_project(data, episode)
            return {"ok": True}

        return update(mutate)

    @staticmethod
    def delete_asset(user: dict, asset_id: str) -> dict:
        if db_store.enabled():
            if not db_store.delete_asset(user, asset_id):
                not_found("asset")
            return {"ok": True}

        def mutate(data):
            asset = find_by_id(data["assets"], asset_id, "asset")
            verify_project_ownership(data, asset["project_id"], user["id"])
            data["assets"] = [a for a in data["assets"] if a["id"] != asset_id]
            return {"ok": True}

        return update(mutate)

    @staticmethod
    def delete_video_version(user: dict, version_id: str) -> dict:
        if db_store.enabled():
            if not db_store.delete_video_version(user, version_id):
                not_found("version")
            return {"ok": True}

        def mutate(data):
            version = find_by_id(data["video_versions"], version_id, "version")
            verify_project_ownership(data, version["project_id"], user["id"])
            data["video_versions"] = [v for v in data["video_versions"] if v["id"] != version_id]
            return {"ok": True}

        return update(mutate)

    # ── COMPLEX WRITE ────────────────────────────────────────────────────

    @staticmethod
    def generate_project_outline(user: dict, episodes: list, cost: int, project_name: str) -> dict:


        if db_store.enabled():
            result = db_store.consume_with_job(
                user["id"], cost, "生成短剧大纲",
                f"智能生成《{project_name}》短剧大纲", "outline", "minimax", now(),
            )
            if result.get("error") == "insufficient_points":
                raise HTTPException(status_code=402, detail=f"积分不足：本次需要 {cost}")
            return {"cost": cost, "episodes": episodes}

        def mutate(data):
            change_points(data, user["id"], -cost, "consume", "生成短剧大纲", f"智能生成《{project_name}》短剧大纲")
            from .services import add_ai_job
            add_ai_job(data, user["id"], "outline", "minimax", cost)
            return {"cost": cost, "episodes": episodes}

        return update(mutate)

    @staticmethod
    def save_storyboard(user: dict, episode_id: str, ai_shots: list[dict], generated_assets: list[dict], storyboard_cost: int, asset_cost: int) -> list[dict]:
        if db_store.enabled():
            result = db_store.save_storyboard(user, episode_id, ai_shots, generated_assets, storyboard_cost, asset_cost, now())
            if result is None:
                not_found("episode")
            if isinstance(result, dict) and result.get("error") == "insufficient_points":
                raise HTTPException(status_code=402, detail="积分不足")
            return result

        from .services import get_user_usage

        def mutate(data):
            target = find_by_id(data["episodes"], episode_id, "episode")
            verify_project_ownership(data, target["project_id"], user["id"])
            for asset in generated_assets:
                duplicate = any(
                    existing.get("project_id") == target["project_id"]
                    and existing.get("type") == asset["type"]
                    and asset["name"] in comparable_asset_names(existing)
                    for existing in data["assets"]
                )
                if duplicate:
                    continue
                change_points(data, user["id"], -asset_cost, "consume", "AI 生成素材", f"AI 生成素材《{asset['name']}》")
                add_ai_job(data, user["id"], "image_asset", "seedream", asset_cost, project_id=target["project_id"], asset_id=asset["id"])
                data["assets"].insert(0, asset)
                usage = get_user_usage(data, user["id"])
                usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)

            change_points(data, user["id"], -storyboard_cost, "consume", "生成分镜", f"生成/更新《{target['title']}》分镜")
            add_ai_job(data, user["id"], "storyboard", "minimax", storyboard_cost, episode_id=episode_id, project_id=target["project_id"])
            data["shots"] = [s for s in data["shots"] if s["episode_id"] != episode_id]
            new_shots = []
            for index, item in enumerate(ai_shots, start=1):
                new_shots.append({
                    "id": uid("shot"),
                    "episode_id": episode_id,
                    "no": index,
                    "title": item["title"],
                    "visual": item.get("visual", ""),
                    "dialogue": item.get("dialogue", ""),
                    "characters": item.get("characters", []),
                    "scene": item.get("scene", ""),
                    "duration": item.get("duration", 3),
                    "status": "pending",
                    "updated_at": now(),
                })
            data["shots"].extend(new_shots)
            target["status"] = "storyboard_ready"
            touch_episode_and_project(data, target)
            return new_shots

        return update(mutate)

    @staticmethod
    def generate_asset(user: dict, project_id: str, payload: Any, generated_url: str | None, refs: list[dict], visual_asset: bool) -> dict:


        cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
        provider = "seedream" if visual_asset else "manual"

        if db_store.enabled():
            asset = db_store.generate_asset(user, project_id, payload, generated_url, refs, cost, provider, now())
            if asset is None:
                not_found("project")
            if asset.get("error") == "insufficient_points":
                raise HTTPException(status_code=402, detail=f"积分不足：本次需要 {cost}")
            return asset

        def mutate(data):
            verify_project_ownership(data, project_id, user["id"])
            change_points(data, user["id"], -cost, "consume", "AI 生成素材", f"AI 生成素材《{payload.name}》")
            add_ai_job(data, user["id"], "image_asset" if visual_asset else "audio_asset", provider, cost, project_id=project_id)
            ts = now()
            asset = {
                "id": uid("asset"),
                "project_id": project_id,
                "type": payload.type,
                "name": payload.name,
                "description": payload.description,
                "ref_count": len(refs),
                "initial": payload.name[:1],
                "image": generated_url,
                "voice": None,
                "voice_url": None,
                "references": refs,
                "updated_at": ts,
            }
            data["assets"].insert(0, asset)
            if visual_asset:
                usage = get_user_usage(data, user["id"])
                usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)
            touch_project(data, project_id, ts)
            return asset

        return update(mutate)

    @staticmethod
    def create_video_task(user: dict, shot_id: str, provider_task_id: str, cost_per_second: int) -> dict:
        if db_store.enabled():
            task = db_store.create_video_task(user, shot_id, provider_task_id, cost_per_second, now())
            if task is None:
                not_found("shot")
            if task.get("error") == "insufficient_points":
                raise HTTPException(status_code=402, detail="积分不足")
            return task

        from .services import add_ai_job

        def mutate(data):
            shot = find_by_id(data["shots"], shot_id, "shot")
            episode = next((e for e in data["episodes"] if e["id"] == shot["episode_id"]), None)
            if episode:
                verify_project_ownership(data, episode["project_id"], user["id"])
            duration = max(1, int(shot["duration"]))
            change_points(data, user["id"], -(duration * cost_per_second), "consume", "生成镜头视频", f"生成镜头 #{shot['no']}《{shot['title']}》，{duration}s")
            job = add_ai_job(
                data, user["id"], "video_shot", "seedance", duration * cost_per_second,
                status="running", progress=0, provider_task_id=provider_task_id,
                episode_id=shot["episode_id"], shot_id=shot["id"],
            )
            task = next((t for t in data["video_tasks"] if t["shot_id"] == shot["id"]), None)
            if not task:
                task = {"id": uid("task"), "episode_id": shot["episode_id"], "shot_id": shot["id"]}
                data["video_tasks"].append(task)
            task.update({
                "title": shot["title"],
                "duration": duration,
                "progress": 0,
                "status": "generating",
                "provider": "seedance",
                "provider_task_id": provider_task_id,
                "ai_job_id": job["id"],
                "error": None,
                "updated_at": now(),
            })
            shot["status"] = "generating"
            shot["updated_at"] = now()
            if episode:
                touch_episode_and_project(data, episode)
            return task

        return update(mutate)

    @staticmethod
    def batch_create_video_tasks(user: dict, episode_id: str, provider_tasks: dict[str, str], cost_per_second: int) -> list[dict]:
        if db_store.enabled():
            tasks = []
            for shot_id, provider_task_id in provider_tasks.items():
                task = db_store.create_video_task(user, shot_id, provider_task_id, cost_per_second, now())
                if isinstance(task, dict) and task.get("error") == "insufficient_points":
                    raise HTTPException(status_code=402, detail="积分不足")
                if task:
                    tasks.append(task)
            return tasks

        from .services import add_ai_job

        def mutate(data):
            target_episode = find_by_id(data["episodes"], episode_id, "episode")
            verify_project_ownership(data, target_episode["project_id"], user["id"])
            target_shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
            total_duration = sum(max(1, int(s["duration"])) for s in target_shots)
            change_points(data, user["id"], -(total_duration * cost_per_second), "consume", "批量生成视频", f"批量生成《{target_episode['title']}》{len(target_shots)} 个镜头，{total_duration}s")
            tasks = []
            for target in target_shots:
                duration = max(1, int(target["duration"]))
                job = add_ai_job(
                    data, user["id"], "video_shot", "seedance", duration * cost_per_second,
                    status="running", progress=0, provider_task_id=provider_tasks[target["id"]],
                    episode_id=episode_id, shot_id=target["id"], project_id=target_episode["project_id"],
                )
                task = next((t for t in data["video_tasks"] if t["shot_id"] == target["id"]), None)
                if not task:
                    task = {"id": uid("task"), "episode_id": target["episode_id"], "shot_id": target["id"]}
                    data["video_tasks"].append(task)
                task.update({
                    "title": target["title"],
                    "duration": max(1, int(target["duration"])),
                    "progress": 0,
                    "status": "generating",
                    "provider": "seedance",
                    "provider_task_id": provider_tasks[target["id"]],
                    "ai_job_id": job["id"],
                    "error": None,
                    "updated_at": now(),
                })
                target["status"] = "generating"
                target["updated_at"] = now()
                tasks.append(task)
            target_episode["status"] = "generating"
            touch_episode_and_project(data, target_episode)
            return tasks

        return update(mutate)

    @staticmethod
    def save_composed_version(user: dict, episode_id: str, payload: Any, video_url: str, cost: int) -> dict:
        if db_store.enabled():
            version = db_store.save_composed_version(user, episode_id, payload, video_url, cost, now())
            if isinstance(version, dict) and version.get("error") == "insufficient_points":
                raise HTTPException(status_code=402, detail="积分不足")
            return version

        from .services import add_ai_job

        def mutate(data):
            target = find_by_id(data["episodes"], episode_id, "episode")
            verify_project_ownership(data, target["project_id"], user["id"])
            change_points(data, user["id"], -cost, "consume", "合成成片", f"合成《{target['title']}》成片版本")
            add_ai_job(data, user["id"], "compose", "ffmpeg", cost, episode_id=episode_id, project_id=target["project_id"])
            version_no = len([v for v in data["video_versions"] if v["episode_id"] == episode_id]) + 1
            version = {
                "id": uid("ver"),
                "project_id": target["project_id"],
                "episode_id": episode_id,
                "name": payload.name if payload.name != "成片版本" else f"第{target['no']:02d}集 版本{chr(64 + version_no)}",
                "description": payload.description,
                "duration": payload.duration,
                "ratio": payload.ratio,
                "status": "exported",
                "theme": "green" if version_no % 2 else "blue",
                "preview_url": video_url,
                "video_url": video_url,
                "created_at": now(),
            }
            data["video_versions"].insert(0, version)
            usage = get_user_usage(data, user["id"])
            usage["export_used"] = min(usage["export_total"], usage["export_used"] + 1)
            touch_episode_and_project(data, target)
            return version

        return update(mutate)

    # ── ADMIN ────────────────────────────────────────────────────────────

    @staticmethod
    def admin_summary() -> dict:
        if db_store.enabled():
            return db_store.admin_summary()
        data = snapshot()
        users = data.get("users", [])
        ledger = data.get("point_ledger", [])
        consumed = -sum(e["amount"] for e in ledger if e["amount"] < 0)
        granted = sum(e["amount"] for e in ledger if e["amount"] > 0)
        return {
            "user_count": len(users),
            "active_user_count": len([u for u in users if u.get("status") == "active"]),
            "total_balance": sum(int(u.get("points", 0)) for u in users),
            "consumed_points": consumed,
            "granted_points": granted,
            "ledger_count": len(ledger),
        }

    @staticmethod
    def admin_users() -> list[dict]:
        if db_store.enabled():
            return db_store.admin_users()
        data = snapshot()
        return [public_user(u) for u in data.get("users", [])]

    @staticmethod
    def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict:
        if db_store.enabled():
            updated = db_store.admin_update_user(user_id, role, status)
            if not updated:
                not_found("user")
            return updated

        from .services import user_in_data

        def mutate(data):
            target = user_in_data(data, user_id)
            if role is not None:
                target["role"] = role
            if status is not None:
                target["status"] = status
            return public_user(target)

        return update(mutate)

    @staticmethod
    def admin_adjust_points(user_id: str, amount: int, reason: str) -> dict:
        if db_store.enabled():
            result = db_store.admin_adjust_points(user_id, amount, reason, now())
            if result is None:
                not_found("user")
            return result

        from .services import user_in_data

        def mutate(data):
            entry = change_points(data, user_id, amount, "admin_adjust", "管理员调整", reason)
            return {"entry": entry, "user": public_user(user_in_data(data, user_id))}

        return update(mutate)

    @staticmethod
    def admin_reset_password(user_id: str, password_hash: str) -> dict:
        if db_store.enabled():
            updated = db_store.admin_reset_password(user_id, password_hash)
            if not updated:
                not_found("user")
            return {"user": updated}

        from .services import user_in_data

        def mutate(data):
            target = user_in_data(data, user_id)
            target["password_hash"] = password_hash
            target["token"] = ""
            return {"user": public_user(target)}

        return update(mutate)

    @staticmethod
    def admin_point_ledger(user_id: str | None = None) -> list[dict]:
        if db_store.enabled():
            return db_store.admin_point_ledger(user_id)
        data = snapshot()
        rows = data.get("point_ledger", [])
        if user_id:
            rows = [r for r in rows if r["user_id"] == user_id]
        return rows[:200]

    # ── AUTH ─────────────────────────────────────────────────────────────

    @staticmethod
    def register_user(username: str, display_name: str, password_hash: str, token: str) -> dict | None:
        if db_store.enabled():
            return db_store.register_user(username, display_name, password_hash, token, now())

        def mutate(data):
            ts = now()
            user = {
                "id": uid("user"),
                "username": username,
                "display_name": display_name,
                "password_hash": password_hash,
                "role": "user",
                "status": "active",
                "points": 0,
                "token": token,
                "created_at": ts,
                "last_login": ts,
            }
            data.setdefault("users", []).append(user)
            change_points(data, user["id"], 1000, "register_bonus", "注册赠送", "新用户注册赠送积分")
            return user

        return update(mutate)

    @staticmethod
    def login_user(username: str, password: str, token: str, last_login: str | None = None) -> dict | None:
        from .security import verify_password

        if db_store.enabled():
            return db_store.login_user(username, password, token, last_login or now())

        def mutate(data):
            user = next((u for u in data.get("users", []) if u["username"].lower() == username.lower()), None)
            if not user or not verify_password(password, user.get("password_hash", "")):
                return None
            if user.get("status") != "active":
                raise HTTPException(status_code=403, detail="账号已被禁用")
            user["token"] = token
            user["last_login"] = now()
            return user

        return update(mutate)

    @staticmethod
    def change_password(user_id: str, current_password: str, new_password: str) -> str:
        from .security import hash_password, verify_password

        if db_store.enabled():
            return db_store.change_password(user_id, current_password, new_password)

        from .services import user_in_data

        def mutate(data):
            target = next((u for u in data.get("users", []) if u["id"] == user_id), None)
            if not target:
                return "missing"
            if not verify_password(current_password, target.get("password_hash", "")):
                return "bad_password"
            target["password_hash"] = hash_password(new_password)
            return "ok"

        return update(mutate)

    @staticmethod
    def point_ledger(user: dict, page: int = 1, page_size: int = 10) -> dict:
        if db_store.enabled():
            return db_store.point_ledger(user, page, page_size)
        data = snapshot()
        rows = [e for e in data.get("point_ledger", []) if e["user_id"] == user["id"]]
        total = len(rows)
        start = (page - 1) * page_size
        return {"items": rows[start:start + page_size], "total": total}

    @staticmethod
    def find_user_by_token(token: str | None) -> dict | None:
        if db_store.enabled():
            return db_store.find_user_by_token(token)
        if not token:
            return None
        data = snapshot()
        return next((u for u in data.get("users", []) if u.get("token") == token), None)
