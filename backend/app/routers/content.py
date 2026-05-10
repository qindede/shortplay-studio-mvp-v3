from __future__ import annotations

from fastapi import APIRouter, Depends

from ..config import POINT_RULES
from ..schemas import (
    AssetCreate,
    ComposeRequest,
    EpisodeCreate,
    EpisodeUpdate,
    OutlineGenerateRequest,
    OutlineGenerateResponse,
    ProjectCreate,
    ShotCreate,
    ShotUpdate,
)
from ..security import get_current_user
from ..services import (
    build_project_outline,
    build_storyboard,
    change_points,
    consume_for_video,
    create_or_complete_video_task,
    enrich_episode,
    enrich_project,
    find_by_id,
    not_found,
    renumber,
    touch_episode_and_project,
    touch_project,
    usage_with_members,
)
from ..store import now, snapshot, uid, update

router = APIRouter(prefix="/api", tags=["content"])


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    data = snapshot()
    return {
        "project_count": len(data["projects"]),
        "episode_count": len(data["episodes"]),
        "version_count": len(data["video_versions"]),
        "asset_count": len(data["assets"]),
        "usage": usage_with_members(data),
        "current_user": user,
    }


@router.get("/projects")
def list_projects(user: dict = Depends(get_current_user)):
    data = snapshot()
    return [enrich_project(data, p) for p in data["projects"]]


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
            data["episodes"].append(
                {
                    "id": uid("ep"),
                    "project_id": project["id"],
                    "no": index,
                    "title": item.title,
                    "summary": item.summary,
                    "script": item.script or item.summary,
                    "duration_target": item.duration_target,
                    "status": "draft",
                    "updated_at": ts,
                }
            )
        return enrich_project(data, project)

    return update(mutate)


@router.post("/projects/generate-outline", response_model=OutlineGenerateResponse)
def generate_project_outline(payload: OutlineGenerateRequest, user: dict = Depends(get_current_user)):
    def mutate(data):
        cost = POINT_RULES["outline"]
        change_points(data, user["id"], -cost, "consume", "生成短剧大纲", f"智能生成《{payload.name}》短剧大纲")
        return {"cost": cost, "episodes": build_project_outline(payload)}

    return update(mutate)


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    return enrich_project(data, find_by_id(data["projects"], project_id, "project"))


@router.get("/projects/{project_id}/episodes")
def list_episodes(project_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    find_by_id(data["projects"], project_id, "project")
    episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
    episodes.sort(key=lambda x: x["no"])
    return [enrich_episode(data, e) for e in episodes]


@router.post("/projects/{project_id}/episodes")
def create_episode(project_id: str, payload: EpisodeCreate, user: dict = Depends(get_current_user)):
    def mutate(data):
        find_by_id(data["projects"], project_id, "project")
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
    return enrich_episode(data, find_by_id(data["episodes"], episode_id, "episode"))


@router.put("/episodes/{episode_id}")
def update_episode(episode_id: str, payload: EpisodeUpdate, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
        for key, value in payload.model_dump(exclude_none=True).items():
            episode[key] = value
        touch_episode_and_project(data, episode)
        return enrich_episode(data, episode)

    return update(mutate)


@router.delete("/episodes/{episode_id}")
def delete_episode(episode_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
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
    find_by_id(data["episodes"], episode_id, "episode")
    shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
    shots.sort(key=lambda x: x["no"])
    return shots


@router.post("/episodes/{episode_id}/shots")
def create_shot(episode_id: str, payload: ShotCreate, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
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


@router.post("/episodes/{episode_id}/generate-storyboard")
def generate_storyboard(episode_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
        change_points(data, user["id"], -POINT_RULES["storyboard"], "consume", "生成分镜", f"生成/更新《{episode['title']}》分镜")
        data["shots"] = [s for s in data["shots"] if s["episode_id"] != episode_id]
        new_shots = build_storyboard(episode)
        data["shots"].extend(new_shots)
        episode["status"] = "storyboard_ready"
        touch_episode_and_project(data, episode)
        return new_shots

    return update(mutate)


@router.patch("/shots/{shot_id}")
def patch_shot(shot_id: str, payload: ShotUpdate, user: dict = Depends(get_current_user)):
    def mutate(data):
        shot = find_by_id(data["shots"], shot_id, "shot")
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

        episode = next((e for e in data["episodes"] if e["id"] == shot["episode_id"]), None)
        if episode:
            touch_episode_and_project(data, episode)
        return shot

    return update(mutate)


@router.delete("/shots/{shot_id}")
def delete_shot(shot_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        shot = find_by_id(data["shots"], shot_id, "shot")
        episode_id = shot["episode_id"]
        data["shots"] = [s for s in data["shots"] if s["id"] != shot_id]
        data["video_tasks"] = [t for t in data["video_tasks"] if t["shot_id"] != shot_id]
        renumber([s for s in data["shots"] if s["episode_id"] == episode_id])

        episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
        if episode:
            touch_episode_and_project(data, episode)
        return {"ok": True}

    return update(mutate)


@router.get("/episodes/{episode_id}/video-tasks")
def list_video_tasks(episode_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    find_by_id(data["episodes"], episode_id, "episode")
    tasks = [t for t in data["video_tasks"] if t["episode_id"] == episode_id]
    tasks.sort(key=lambda x: x["updated_at"], reverse=True)
    return tasks


@router.post("/shots/{shot_id}/generate-video")
def generate_video_for_shot(shot_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        shot = find_by_id(data["shots"], shot_id, "shot")
        consume_for_video(
            data,
            user["id"],
            [shot],
            "生成镜头视频",
            f"生成镜头 #{shot['no']}《{shot['title']}》，{shot['duration']}s",
        )
        task = create_or_complete_video_task(data, shot)
        episode = next((e for e in data["episodes"] if e["id"] == shot["episode_id"]), None)
        if episode:
            touch_episode_and_project(data, episode)
        return task

    return update(mutate)


@router.post("/episodes/{episode_id}/generate-videos")
def generate_all_videos(episode_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
        shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        if not shots:
            not_found("shots")

        total_duration = sum(max(1, int(s["duration"])) for s in shots)
        consume_for_video(
            data,
            user["id"],
            shots,
            "批量生成视频",
            f"批量生成《{episode['title']}》{len(shots)} 个镜头，{total_duration}s",
        )
        tasks = [create_or_complete_video_task(data, shot) for shot in shots]
        episode["status"] = "completed"
        touch_episode_and_project(data, episode)
        return tasks

    return update(mutate)


@router.get("/projects/{project_id}/assets")
def list_assets(project_id: str, type: str | None = None, user: dict = Depends(get_current_user)):
    data = snapshot()
    find_by_id(data["projects"], project_id, "project")
    assets = [a for a in data["assets"] if a["project_id"] == project_id]
    if type:
        assets = [a for a in assets if a["type"] == type]
    return assets


@router.post("/projects/{project_id}/assets")
def create_asset(project_id: str, payload: AssetCreate, user: dict = Depends(get_current_user)):
    def mutate(data):
        find_by_id(data["projects"], project_id, "project")
        visual_asset = payload.type in {"character", "scene", "image"}
        cost = POINT_RULES["image_asset"] if visual_asset else POINT_RULES["audio_asset"]
        scene = "创建视觉素材" if visual_asset else "创建音频素材"
        change_points(data, user["id"], -cost, "consume", scene, f"创建素材《{payload.name}》")

        ts = now()
        asset = {
            "id": uid("asset"),
            "project_id": project_id,
            "type": payload.type,
            "name": payload.name,
            "description": payload.description,
            "ref_count": 0,
            "initial": payload.initial[:1] or payload.name[:1],
            "updated_at": ts,
        }
        data["assets"].insert(0, asset)
        if visual_asset:
            data["usage"]["image_used"] = min(data["usage"]["image_total"], data["usage"]["image_used"] + 1)
        touch_project(data, project_id, ts)
        return asset

    return update(mutate)


@router.get("/projects/{project_id}/video-versions")
def list_video_versions(project_id: str, episode_id: str | None = None, user: dict = Depends(get_current_user)):
    data = snapshot()
    find_by_id(data["projects"], project_id, "project")
    versions = [v for v in data["video_versions"] if v["project_id"] == project_id]
    if episode_id:
        versions = [v for v in versions if v["episode_id"] == episode_id]
    versions.sort(key=lambda x: x["created_at"], reverse=True)
    return versions


@router.post("/episodes/{episode_id}/compose")
def compose_episode(episode_id: str, payload: ComposeRequest, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = find_by_id(data["episodes"], episode_id, "episode")
        change_points(data, user["id"], -POINT_RULES["compose"], "consume", "合成成片", f"合成《{episode['title']}》成片版本")
        version_no = len([v for v in data["video_versions"] if v["episode_id"] == episode_id]) + 1
        version = {
            "id": uid("ver"),
            "project_id": episode["project_id"],
            "episode_id": episode_id,
            "name": payload.name if payload.name != "成片版本" else f"第{episode['no']:02d}集 版本{chr(64 + version_no)}",
            "description": payload.description,
            "duration": payload.duration,
            "ratio": payload.ratio,
            "status": "review",
            "theme": "green" if version_no % 2 else "blue",
            "created_at": now(),
        }
        data["video_versions"].insert(0, version)
        data["usage"]["export_used"] = min(data["usage"]["export_total"], data["usage"]["export_used"] + 1)
        touch_episode_and_project(data, episode)
        return version

    return update(mutate)


@router.get("/usage")
def usage(user: dict = Depends(get_current_user)):
    data = snapshot()
    return usage_with_members(data)


@router.get("/point-rules")
def point_rules(user: dict = Depends(get_current_user)):
    return POINT_RULES
