from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .. import db_store, storage
from ..ai import image as ai_image
from ..ai import llm as ai_llm
from ..ai import video as ai_video
from ..ai import voice as ai_voice
from ..ai.errors import AIError
from ..config import BACKEND_PUBLIC_URL, FFMPEG_PATH, POINT_RULES
from ..schemas import (
    AssetCreate,
    AssetGenerate,
    AssetUpdate,
    ComposeRequest,
    EpisodeCreate,
    EpisodeUpdate,
    OutlineGenerateRequest,
    OutlineGenerateResponse,
    ProjectCreate,
    ProjectUpdate,
    PromptOptimizeRequest,
    ShotCreate,
    ShotUpdate,
    StoryboardGenerateRequest,
    StoryboardPrepareResponse,
    VoiceCloneRequest,
)
from ..security import get_current_user
from ..services import (
    change_points,
    enrich_episode,
    enrich_project,
    find_by_id,
    get_user_projects,
    get_user_usage,
    not_found,
    renumber,
    touch_episode_and_project,
    touch_project,
    usage_with_members,
    verify_project_ownership,
)
from ..store import now, snapshot, uid, update

router = APIRouter(prefix="/api", tags=["content"])


def ai_error(exc: AIError) -> HTTPException:
    return HTTPException(status_code=503, detail=exc.public_message)


def add_ai_job(
    data: dict,
    user_id: str,
    job_type: str,
    provider: str,
    cost: int,
    status: str = "succeeded",
    progress: int = 100,
    provider_task_id: str | None = None,
    error: str | None = None,
    **links,
) -> dict:
    ts = now()
    job = {
        "id": uid("job"),
        "user_id": user_id,
        "type": job_type,
        "provider": provider,
        "provider_task_id": provider_task_id,
        "status": status,
        "progress": progress,
        "cost_points": cost,
        "input_json": {},
        "output_json": {},
        "error": error,
        "created_at": ts,
        "updated_at": ts,
        "completed_at": ts if status in {"succeeded", "failed", "cancelled"} else "",
        **{key: value for key, value in links.items() if value},
    }
    data.setdefault("ai_jobs", []).insert(0, job)
    return job


def refund_once(data: dict, user_id: str, task: dict, amount: int, scene: str, description: str) -> None:
    output_json = task.get("output_json") if isinstance(task.get("output_json"), dict) else {}
    if task.get("refunded") or output_json.get("refunded") or amount <= 0:
        return
    change_points(data, user_id, amount, "refund", scene, description)
    task["refunded"] = True
    if "output_json" in task:
        output_json["refunded"] = True
        task["output_json"] = output_json


def normalize_refs(refs: list[dict] | None) -> list[dict]:
    normalized = []
    for index, ref in enumerate(refs or [], start=1):
        normalized.append({
            "id": ref.get("id") or uid("ref"),
            "type": ref.get("type", "image"),
            "name": ref.get("name") or f"参考 {index:02d}",
            "url": ref.get("url"),
            "note": ref.get("note"),
        })
    return normalized


def provider_media_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/uploads/") and BACKEND_PUBLIC_URL:
        return f"{BACKEND_PUBLIC_URL.rstrip('/')}{url}"
    return None


def find_reference_image(data: dict, shot: dict) -> str | None:
    episode = next((item for item in data.get("episodes", []) if item["id"] == shot["episode_id"]), None)
    if not episode:
        return None
    assets = [item for item in data.get("assets", []) if item.get("project_id") == episode["project_id"]]
    character_names = {name.strip() for name in shot.get("characters", []) if name.strip()}
    scene = (shot.get("scene") or "").strip()
    candidates = []
    if character_names:
        candidates.extend(asset for asset in assets if asset.get("type") == "character" and asset.get("name") in character_names)
    if scene:
        candidates.extend(asset for asset in assets if asset.get("type") == "scene" and asset.get("name") == scene)
    candidates.extend(asset for asset in assets if asset.get("type") in {"image", "scene", "character"})
    for asset in candidates:
        media_url = provider_media_url(asset.get("image"))
        if media_url:
            return media_url
    return None


def comparable_asset_names(asset: dict) -> set[str]:
    name = (asset.get("name") or "").strip()
    names = {name}
    if "：" in name:
        names.add(name.rsplit("：", 1)[-1].strip())
    if ":" in name:
        names.add(name.rsplit(":", 1)[-1].strip())
    return {item for item in names if item}


def storyboard_missing_assets(ai_shots: list[dict], assets: list[dict]) -> list[dict]:
    existing = {
        "character": set().union(*(comparable_asset_names(asset) for asset in assets if asset.get("type") == "character")),
        "scene": set().union(*(comparable_asset_names(asset) for asset in assets if asset.get("type") == "scene")),
    }
    missing: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add_candidate(asset_type: str, name: str, description: str) -> None:
        clean_name = name.strip()
        if not clean_name or clean_name in existing[asset_type]:
            return
        key = (asset_type, clean_name)
        if key in seen:
            return
        seen.add(key)
        label = "角色" if asset_type == "character" else "场景"
        missing.append({
            "type": asset_type,
            "name": clean_name,
            "description": description or f"本集分镜中出现的新{label}",
            "prompt": f"{clean_name}，{description or f'短剧本集需要使用的新{label}'}",
        })

    for shot in ai_shots:
        visual = shot.get("visual", "")
        dialogue = shot.get("dialogue", "")
        context = "；".join(part for part in [visual, dialogue] if part)
        for character in shot.get("characters") or []:
            add_candidate("character", str(character), context)
        add_candidate("scene", str(shot.get("scene") or ""), visual)

    return missing


def create_generated_asset_payload(project_id: str, payload: dict, generated_url: str | None) -> dict:
    visual_asset = payload["type"] in {"character", "scene", "image"}
    ts = now()
    refs = [{
        "id": uid("ref"),
        "type": "image" if visual_asset else "audio",
        "name": f"AI 生成 - {payload['name']}",
        "url": generated_url,
        "note": payload["prompt"],
    }]
    return {
        "id": uid("asset"),
        "project_id": project_id,
        "type": payload["type"],
        "name": payload["name"],
        "description": payload.get("description", ""),
        "ref_count": len(refs),
        "initial": payload["name"][:1],
        "image": generated_url,
        "voice": None,
        "voice_url": None,
        "references": refs,
        "updated_at": ts,
    }


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
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


@router.get("/workspace/bootstrap")
def workspace_bootstrap(user: dict = Depends(get_current_user)):
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
                v
                for v in data["video_versions"]
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


@router.post("/optimize-prompt")
def optimize_prompt_endpoint(payload: PromptOptimizeRequest, user: dict = Depends(get_current_user)):
    try:
        return {"optimized": ai_llm.optimize_prompt(payload.prompt, payload.context, payload.project_name)}
    except AIError as exc:
        raise ai_error(exc) from exc


@router.get("/projects")
def list_projects(user: dict = Depends(get_current_user)):
    data = snapshot()
    return [enrich_project(data, p) for p in get_user_projects(data, user["id"])]


@router.post("/projects")
def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
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


@router.post("/projects/generate-outline", response_model=OutlineGenerateResponse)
def generate_project_outline(payload: OutlineGenerateRequest, user: dict = Depends(get_current_user)):
    try:
        episodes = ai_llm.generate_outline(payload)
    except AIError as exc:
        raise ai_error(exc) from exc

    def mutate(data):
        cost = POINT_RULES["outline"]
        change_points(data, user["id"], -cost, "consume", "生成短剧大纲", f"智能生成《{payload.name}》短剧大纲")
        add_ai_job(data, user["id"], "outline", "minimax", cost)
        return {"cost": cost, "episodes": episodes}

    return update(mutate)


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    return enrich_project(data, verify_project_ownership(data, project_id, user["id"]))


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, user: dict = Depends(get_current_user)):
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


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user: dict = Depends(get_current_user)):
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


@router.get("/projects/{project_id}/episodes")
def list_episodes(project_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    verify_project_ownership(data, project_id, user["id"])
    episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
    episodes.sort(key=lambda x: x["no"])
    return [enrich_episode(data, e) for e in episodes]


@router.post("/projects/{project_id}/episodes")
def create_episode(project_id: str, payload: EpisodeCreate, user: dict = Depends(get_current_user)):
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


@router.get("/episodes/{episode_id}")
def get_episode(episode_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    episode = find_by_id(data["episodes"], episode_id, "episode")
    verify_project_ownership(data, episode["project_id"], user["id"])
    return enrich_episode(data, episode)


@router.put("/episodes/{episode_id}")
def update_episode(episode_id: str, payload: EpisodeUpdate, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
        verify_project_ownership(data, episode["project_id"], user["id"])
        episode.update(payload.model_dump(exclude_none=True))
        touch_episode_and_project(data, episode)
        return enrich_episode(data, episode)

    return update(mutate)


@router.delete("/episodes/{episode_id}")
def delete_episode(episode_id: str, user: dict = Depends(get_current_user)):
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


@router.get("/episodes/{episode_id}/shots")
def list_shots(episode_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    episode = find_by_id(data["episodes"], episode_id, "episode")
    verify_project_ownership(data, episode["project_id"], user["id"])
    shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
    shots.sort(key=lambda x: x["no"])
    return shots


@router.post("/episodes/{episode_id}/shots")
def create_shot(episode_id: str, payload: ShotCreate, user: dict = Depends(get_current_user)):
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


@router.post("/episodes/{episode_id}/prepare-storyboard", response_model=StoryboardPrepareResponse)
def prepare_storyboard(episode_id: str, user: dict = Depends(get_current_user)):
    current = snapshot()
    episode = find_by_id(current["episodes"], episode_id, "episode")
    project = verify_project_ownership(current, episode["project_id"], user["id"])
    assets = [a for a in current["assets"] if a["project_id"] == project["id"]]
    try:
        ai_shots = ai_llm.generate_storyboard(project, episode, assets)
    except AIError as exc:
        raise ai_error(exc) from exc
    return {
        "cost": POINT_RULES["storyboard"],
        "asset_cost": POINT_RULES["image_asset"],
        "missing_assets": storyboard_missing_assets(ai_shots, assets),
    }


@router.post("/episodes/{episode_id}/generate-storyboard")
def generate_storyboard(episode_id: str, payload: StoryboardGenerateRequest | None = None, user: dict = Depends(get_current_user)):
    current = snapshot()
    episode = find_by_id(current["episodes"], episode_id, "episode")
    project = verify_project_ownership(current, episode["project_id"], user["id"])
    existing_assets = [a for a in current["assets"] if a["project_id"] == project["id"]]
    confirmed_assets = [item.model_dump() for item in (payload.confirmed_assets if payload else [])]
    existing_names = {
        item
        for asset in existing_assets
        for item in comparable_asset_names(asset)
        if asset.get("type") in {"character", "scene"}
    }
    assets_to_generate = [item for item in confirmed_assets if item["name"].strip() not in existing_names]
    generated_assets: list[dict] = []
    for item in assets_to_generate:
        try:
            generated_url = ai_image.generate_image(item["prompt"])
        except AIError as exc:
            raise ai_error(exc) from exc
        generated_assets.append(create_generated_asset_payload(project["id"], item, generated_url))

    storyboard_assets = existing_assets + generated_assets
    try:
        ai_shots = ai_llm.generate_storyboard(project, episode, storyboard_assets)
    except AIError as exc:
        raise ai_error(exc) from exc

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
            asset_cost = POINT_RULES["image_asset"]
            change_points(data, user["id"], -asset_cost, "consume", "AI 生成素材", f"AI 生成素材《{asset['name']}》")
            add_ai_job(data, user["id"], "image_asset", "seedream", asset_cost, project_id=target["project_id"], asset_id=asset["id"])
            data["assets"].insert(0, asset)
            usage = get_user_usage(data, user["id"])
            usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)

        cost = POINT_RULES["storyboard"]
        change_points(data, user["id"], -cost, "consume", "生成分镜", f"生成/更新《{target['title']}》分镜")
        add_ai_job(data, user["id"], "storyboard", "minimax", cost, episode_id=episode_id, project_id=target["project_id"])
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


@router.patch("/shots/{shot_id}")
def patch_shot(shot_id: str, payload: ShotUpdate, user: dict = Depends(get_current_user)):
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


@router.delete("/shots/{shot_id}")
def delete_shot(shot_id: str, user: dict = Depends(get_current_user)):
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


@router.get("/episodes/{episode_id}/video-tasks")
def list_video_tasks(episode_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
        verify_project_ownership(data, episode["project_id"], user["id"])
        tasks = [t for t in data["video_tasks"] if t["episode_id"] == episode_id]
        for task in tasks:
            if task.get("status") != "generating" or not task.get("provider_task_id"):
                continue
            try:
                remote = ai_video.query_video_task(task["provider_task_id"])
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
                refund_once(data, user["id"], refund_target, task["duration"] * POINT_RULES["video_second"], "视频生成失败退款", task.get("error") or "视频任务失败")
        tasks.sort(key=lambda x: x["updated_at"], reverse=True)
        return tasks

    return update(mutate)


@router.post("/shots/{shot_id}/generate-video")
def generate_video_for_shot(shot_id: str, user: dict = Depends(get_current_user)):
    current = snapshot()
    shot = find_by_id(current["shots"], shot_id, "shot")
    episode = next((e for e in current["episodes"] if e["id"] == shot["episode_id"]), None)
    if episode:
        verify_project_ownership(current, episode["project_id"], user["id"])
    image_url = find_reference_image(current, shot)
    try:
        provider_task_id = ai_video.create_video_task(shot.get("visual") or shot["title"], image_url, shot["duration"])
    except AIError as exc:
        raise ai_error(exc) from exc

    def mutate(data):
        target = find_by_id(data["shots"], shot_id, "shot")
        episode_for_shot = next((e for e in data["episodes"] if e["id"] == target["episode_id"]), None)
        if episode_for_shot:
            verify_project_ownership(data, episode_for_shot["project_id"], user["id"])
        duration = max(1, int(target["duration"]))
        change_points(data, user["id"], -(duration * POINT_RULES["video_second"]), "consume", "生成镜头视频", f"生成镜头 #{target['no']}《{target['title']}》，{duration}s")
        job = add_ai_job(
            data,
            user["id"],
            "video_shot",
            "seedance",
            duration * POINT_RULES["video_second"],
            status="running",
            progress=0,
            provider_task_id=provider_task_id,
            episode_id=target["episode_id"],
            shot_id=target["id"],
        )
        task = next((t for t in data["video_tasks"] if t["shot_id"] == target["id"]), None)
        if not task:
            task = {"id": uid("task"), "episode_id": target["episode_id"], "shot_id": target["id"]}
            data["video_tasks"].append(task)
        task.update({
            "title": target["title"],
            "duration": duration,
            "progress": 0,
            "status": "generating",
            "provider": "seedance",
            "provider_task_id": provider_task_id,
            "ai_job_id": job["id"],
            "error": None,
            "updated_at": now(),
        })
        target["status"] = "generating"
        target["updated_at"] = now()
        if episode_for_shot:
            touch_episode_and_project(data, episode_for_shot)
        return task

    return update(mutate)


@router.post("/episodes/{episode_id}/generate-videos")
def generate_all_videos(episode_id: str, user: dict = Depends(get_current_user)):
    current = snapshot()
    episode = find_by_id(current["episodes"], episode_id, "episode")
    verify_project_ownership(current, episode["project_id"], user["id"])
    shots = [s for s in current["shots"] if s["episode_id"] == episode_id]
    if not shots:
        not_found("shots")
    try:
        provider_tasks = {
            shot["id"]: ai_video.create_video_task(shot.get("visual") or shot["title"], find_reference_image(current, shot), shot["duration"])
            for shot in shots
        }
    except AIError as exc:
        raise ai_error(exc) from exc

    def mutate(data):
        target_episode = find_by_id(data["episodes"], episode_id, "episode")
        verify_project_ownership(data, target_episode["project_id"], user["id"])
        target_shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        total_duration = sum(max(1, int(s["duration"])) for s in target_shots)
        change_points(data, user["id"], -(total_duration * POINT_RULES["video_second"]), "consume", "批量生成视频", f"批量生成《{target_episode['title']}》{len(target_shots)} 个镜头，{total_duration}s")
        tasks = []
        for target in target_shots:
            duration = max(1, int(target["duration"]))
            job = add_ai_job(
                data,
                user["id"],
                "video_shot",
                "seedance",
                duration * POINT_RULES["video_second"],
                status="running",
                progress=0,
                provider_task_id=provider_tasks[target["id"]],
                episode_id=episode_id,
                shot_id=target["id"],
                project_id=target_episode["project_id"],
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


@router.get("/projects/{project_id}/assets")
def list_assets(project_id: str, type: str | None = None, user: dict = Depends(get_current_user)):
    data = snapshot()
    verify_project_ownership(data, project_id, user["id"])
    assets = [a for a in data["assets"] if a["project_id"] == project_id]
    if type:
        assets = [a for a in assets if a["type"] == type]
    return assets


@router.post("/projects/{project_id}/assets")
def create_asset(project_id: str, payload: AssetCreate, user: dict = Depends(get_current_user)):
    def mutate(data):
        verify_project_ownership(data, project_id, user["id"])
        visual_asset = payload.type in {"character", "scene", "image"}
        cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
        change_points(data, user["id"], -cost, "consume", "创建素材", f"创建素材《{payload.name}》")
        ts = now()
        refs = normalize_refs(payload.references)
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


@router.post("/projects/{project_id}/assets/generate")
def generate_asset(project_id: str, payload: AssetGenerate, user: dict = Depends(get_current_user)):
    visual_asset = payload.type in {"character", "scene", "image"}
    if visual_asset:
        try:
            generated_url = ai_image.generate_image(payload.prompt)
        except AIError as exc:
            raise ai_error(exc) from exc
    else:
        generated_url = None

    def mutate(data):
        verify_project_ownership(data, project_id, user["id"])
        cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
        change_points(data, user["id"], -cost, "consume", "AI 生成素材", f"AI 生成素材《{payload.name}》")
        add_ai_job(data, user["id"], "image_asset" if visual_asset else "audio_asset", "seedream" if visual_asset else "manual", cost, project_id=project_id)
        ts = now()
        refs = [{
            "id": uid("ref"),
            "type": "image" if visual_asset else "audio",
            "name": f"AI 生成 - {payload.name}",
            "url": generated_url,
            "note": payload.prompt,
        }]
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


@router.put("/assets/{asset_id}")
def update_asset(asset_id: str, payload: AssetUpdate, user: dict = Depends(get_current_user)):
    def mutate(data):
        asset = find_by_id(data["assets"], asset_id, "asset")
        verify_project_ownership(data, asset["project_id"], user["id"])
        update_data = payload.model_dump(exclude_unset=True)
        if "references" in update_data and update_data["references"] is not None:
            update_data["references"] = normalize_refs(update_data["references"])
            update_data["ref_count"] = len(update_data["references"])
        asset.update(update_data)
        asset["updated_at"] = now()
        touch_project(data, asset["project_id"], asset["updated_at"])
        return asset

    return update(mutate)


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        asset = find_by_id(data["assets"], asset_id, "asset")
        verify_project_ownership(data, asset["project_id"], user["id"])
        data["assets"] = [a for a in data["assets"] if a["id"] != asset_id]
        return {"ok": True}

    return update(mutate)


@router.post("/assets/{asset_id}/voice-clone")
def start_voice_clone(asset_id: str, payload: VoiceCloneRequest, user: dict = Depends(get_current_user)):
    if not payload.consent:
        raise HTTPException(status_code=400, detail="请确认已获得声音授权")
    current = snapshot()
    asset = find_by_id(current["assets"], asset_id, "asset")
    verify_project_ownership(current, asset["project_id"], user["id"])
    voice_url = payload.voice_url or asset.get("voice_url")
    if not voice_url or not voice_url.startswith("/uploads/"):
        raise HTTPException(status_code=400, detail="请先上传角色声音样本")
    try:
        audio, _ = storage.get_object(voice_url.removeprefix("/uploads/"))
        speaker_id = asset.get("speaker_id") or f"S_{asset_id.replace('-', '_')}_{uid('voice')[-10:]}"
        result = ai_voice.clone_voice(speaker_id, audio, Path(voice_url).suffix.lstrip(".") or "wav")
    except (AIError, storage.StorageError) as exc:
        raise HTTPException(status_code=503, detail=getattr(exc, "public_message", str(exc))) from exc

    def mutate(data):
        target = find_by_id(data["assets"], asset_id, "asset")
        verify_project_ownership(data, target["project_id"], user["id"])
        cost = POINT_RULES["voice_clone"]
        change_points(data, user["id"], -cost, "consume", "音色克隆", f"训练《{target['name']}》角色音色")
        target.update({k: v for k, v in result.items() if v is not None})
        target["updated_at"] = now()
        job = add_ai_job(
            data,
            user["id"],
            "voice_clone",
            "volc_voice",
            cost,
            status="succeeded" if target.get("voice_status") == "completed" else "running",
            progress=100 if target.get("voice_status") == "completed" else 0,
            provider_task_id=target.get("speaker_id"),
            project_id=target["project_id"],
            asset_id=asset_id,
        )
        if job["status"] == "running":
            job["completed_at"] = ""
        return target

    return update(mutate)


@router.get("/assets/{asset_id}/voice-clone")
def get_voice_clone(asset_id: str, user: dict = Depends(get_current_user)):
    current = snapshot()
    asset = find_by_id(current["assets"], asset_id, "asset")
    verify_project_ownership(current, asset["project_id"], user["id"])
    if not asset.get("speaker_id"):
        return asset
    try:
        result = ai_voice.get_voice(asset["speaker_id"])
    except AIError as exc:
        raise ai_error(exc) from exc

    def mutate(data):
        target = find_by_id(data["assets"], asset_id, "asset")
        verify_project_ownership(data, target["project_id"], user["id"])
        target.update({k: v for k, v in result.items() if v is not None})
        target["updated_at"] = now()
        job = next(
            (
                item
                for item in data.get("ai_jobs", [])
                if item.get("asset_id") == asset_id and item.get("type") == "voice_clone" and item.get("status") == "running"
            ),
            None,
        )
        if job:
            job["progress"] = 100 if target.get("voice_status") == "completed" else job.get("progress", 0)
            job["updated_at"] = target["updated_at"]
            if target.get("voice_status") == "completed":
                job["status"] = "succeeded"
                job["completed_at"] = target["updated_at"]
                job["output_json"] = {"voice_url": target.get("voice_url"), "speaker_id": target.get("speaker_id")}
            elif target.get("voice_status") == "failed":
                job["status"] = "failed"
                job["error"] = result.get("error")
                job["completed_at"] = target["updated_at"]
                refund_once(data, user["id"], job, job.get("cost_points", 0), "音色克隆失败退款", result.get("error") or "音色训练失败")
        return target

    return update(mutate)


@router.get("/projects/{project_id}/video-versions")
def list_video_versions(project_id: str, episode_id: str | None = None, user: dict = Depends(get_current_user)):
    data = snapshot()
    verify_project_ownership(data, project_id, user["id"])
    versions = [v for v in data["video_versions"] if v["project_id"] == project_id]
    if episode_id:
        versions = [v for v in versions if v["episode_id"] == episode_id]
    versions.sort(key=lambda x: x["created_at"], reverse=True)
    return versions


@router.delete("/video-versions/{version_id}")
def delete_video_version(version_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        version = find_by_id(data["video_versions"], version_id, "version")
        verify_project_ownership(data, version["project_id"], user["id"])
        data["video_versions"] = [v for v in data["video_versions"] if v["id"] != version_id]
        return {"ok": True}

    return update(mutate)


def compose_video_file(tasks: list[dict]) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        inputs = []
        for index, task in enumerate(tasks, start=1):
            url = task.get("video_url") or task.get("preview_url")
            if not url or not url.startswith("/uploads/"):
                raise HTTPException(status_code=400, detail="镜头视频文件不完整，无法合成")
            data, _ = storage.get_object(url.removeprefix("/uploads/"))
            path = tmpdir / f"{index:03d}.mp4"
            path.write_bytes(data)
            inputs.append(path)
        concat = tmpdir / "inputs.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in inputs), encoding="utf-8")
        output = tmpdir / "episode.mp4"
        try:
            subprocess.run(
                [FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(output)],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail="服务器未配置 ffmpeg") from exc
        except subprocess.CalledProcessError as exc:
            raise HTTPException(status_code=503, detail="视频合成失败") from exc
        key = storage.make_object_key("composed", "episode.mp4", ".mp4")
        return storage.put_bytes(output.read_bytes(), key, "video/mp4")


@router.post("/episodes/{episode_id}/compose")
def compose_episode(episode_id: str, payload: ComposeRequest, user: dict = Depends(get_current_user)):
    current = snapshot()
    episode = find_by_id(current["episodes"], episode_id, "episode")
    verify_project_ownership(current, episode["project_id"], user["id"])
    tasks = [t for t in current["video_tasks"] if t["episode_id"] == episode_id]
    shots = [s for s in current["shots"] if s["episode_id"] == episode_id]
    if not shots or any(s.get("status") != "completed" for s in shots):
        raise HTTPException(status_code=400, detail="所有镜头完成后才能合成本集视频")
    shot_order = {shot["id"]: shot["no"] for shot in shots}
    video_url = compose_video_file(sorted(tasks, key=lambda item: shot_order.get(item.get("shot_id"), 0)))

    def mutate(data):
        target = find_by_id(data["episodes"], episode_id, "episode")
        verify_project_ownership(data, target["project_id"], user["id"])
        cost = POINT_RULES["compose"]
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


@router.get("/ai-jobs/{job_id}")
def get_ai_job(job_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    job = find_by_id(data.get("ai_jobs", []), job_id, "ai job")
    if job.get("user_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return job


@router.get("/projects/{project_id}/ai-jobs")
def list_project_ai_jobs(project_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    verify_project_ownership(data, project_id, user["id"])
    return [job for job in data.get("ai_jobs", []) if job.get("project_id") == project_id][:100]


@router.get("/usage")
def usage(user: dict = Depends(get_current_user)):
    data = snapshot()
    return usage_with_members(data, user["id"])


@router.get("/point-rules")
def point_rules(user: dict = Depends(get_current_user)):
    return POINT_RULES
