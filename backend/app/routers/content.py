from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .. import storage
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
    comparable_asset_names,
    normalize_refs,
    not_found,
)
from ..storage_adapter import Storage
from ..utils import now, uid

router = APIRouter(prefix="/api", tags=["content"])


def ai_error(exc: AIError) -> HTTPException:
    return HTTPException(status_code=503, detail=exc.public_message)


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
    return Storage.dashboard(user)


@router.get("/workspace/bootstrap")
def workspace_bootstrap(user: dict = Depends(get_current_user)):
    return Storage.workspace_bootstrap(user)


@router.post("/optimize-prompt")
def optimize_prompt_endpoint(payload: PromptOptimizeRequest, user: dict = Depends(get_current_user)):
    try:
        return {"optimized": ai_llm.optimize_prompt(payload.prompt, payload.context, payload.project_name)}
    except AIError as exc:
        raise ai_error(exc) from exc


@router.get("/projects")
def list_projects(user: dict = Depends(get_current_user)):
    return Storage.list_projects(user)


@router.post("/projects")
def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
    return Storage.create_project(user, payload)


@router.post("/projects/generate-outline", response_model=OutlineGenerateResponse)
def generate_project_outline(payload: OutlineGenerateRequest, user: dict = Depends(get_current_user)):
    try:
        episodes = ai_llm.generate_outline(payload)
    except AIError as exc:
        raise ai_error(exc) from exc
    return Storage.generate_project_outline(user, episodes, POINT_RULES["outline"], payload.name)


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: dict = Depends(get_current_user)):
    return Storage.get_project(user, project_id)


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, user: dict = Depends(get_current_user)):
    return Storage.update_project(user, project_id, payload)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    return Storage.delete_project(user, project_id)


@router.get("/projects/{project_id}/episodes")
def list_episodes(project_id: str, user: dict = Depends(get_current_user)):
    return Storage.list_episodes(user, project_id)


@router.post("/projects/{project_id}/episodes")
def create_episode(project_id: str, payload: EpisodeCreate, user: dict = Depends(get_current_user)):
    return Storage.create_episode(user, project_id, payload)


@router.get("/episodes/{episode_id}")
def get_episode(episode_id: str, user: dict = Depends(get_current_user)):
    return Storage.get_episode(user, episode_id)


@router.get("/episodes/{episode_id}/workspace")
def get_episode_workspace(episode_id: str, user: dict = Depends(get_current_user)):
    return Storage.episode_workspace(user, episode_id)


@router.put("/episodes/{episode_id}")
def update_episode(episode_id: str, payload: EpisodeUpdate, user: dict = Depends(get_current_user)):
    return Storage.update_episode(user, episode_id, payload)


@router.delete("/episodes/{episode_id}")
def delete_episode(episode_id: str, user: dict = Depends(get_current_user)):
    return Storage.delete_episode(user, episode_id)


@router.get("/episodes/{episode_id}/shots")
def list_shots(episode_id: str, user: dict = Depends(get_current_user)):
    return Storage.list_shots(user, episode_id)


@router.post("/episodes/{episode_id}/shots")
def create_shot(episode_id: str, payload: ShotCreate, user: dict = Depends(get_current_user)):
    return Storage.create_shot(user, episode_id, payload)


@router.post("/episodes/{episode_id}/prepare-storyboard", response_model=StoryboardPrepareResponse)
def prepare_storyboard(episode_id: str, user: dict = Depends(get_current_user)):
    context = Storage.episode_generation_context(user, episode_id)
    if not context:
        not_found("episode")
    try:
        ai_shots = ai_llm.generate_storyboard(context["project"], context["episode"], context["assets"])
    except AIError as exc:
        raise ai_error(exc) from exc
    return {
        "cost": POINT_RULES["storyboard"],
        "asset_cost": POINT_RULES["image_asset"],
        "missing_assets": storyboard_missing_assets(ai_shots, context["assets"]),
    }


@router.post("/episodes/{episode_id}/generate-storyboard")
def generate_storyboard(episode_id: str, payload: StoryboardGenerateRequest | None = None, user: dict = Depends(get_current_user)):
    context = Storage.episode_generation_context(user, episode_id)
    if not context:
        not_found("episode")
    existing_assets = context["assets"]
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
        generated_assets.append(create_generated_asset_payload(context["project"]["id"], item, generated_url))
    try:
        ai_shots = ai_llm.generate_storyboard(context["project"], context["episode"], existing_assets + generated_assets)
    except AIError as exc:
        raise ai_error(exc) from exc
    return Storage.save_storyboard(user, episode_id, ai_shots, generated_assets, POINT_RULES["storyboard"], POINT_RULES["image_asset"])


@router.patch("/shots/{shot_id}")
def patch_shot(shot_id: str, payload: ShotUpdate, user: dict = Depends(get_current_user)):
    return Storage.patch_shot(user, shot_id, payload)


@router.delete("/shots/{shot_id}")
def delete_shot(shot_id: str, user: dict = Depends(get_current_user)):
    return Storage.delete_shot(user, shot_id)


@router.get("/episodes/{episode_id}/video-tasks")
def list_video_tasks(episode_id: str, user: dict = Depends(get_current_user)):
    return Storage.list_video_tasks_with_poll(user, episode_id)


@router.post("/shots/{shot_id}/generate-video")
def generate_video_for_shot(shot_id: str, user: dict = Depends(get_current_user)):
    shot, episode, assets = Storage.get_shot_with_context(user, shot_id)
    data = {"episodes": [episode] if episode else [], "assets": assets}
    try:
        provider_task_id = ai_video.create_video_task(shot.get("visual") or shot["title"], find_reference_image(data, shot), shot["duration"])
    except AIError as exc:
        raise ai_error(exc) from exc
    return Storage.create_video_task(user, shot_id, provider_task_id, POINT_RULES["video_second"])


@router.post("/episodes/{episode_id}/generate-videos")
def generate_all_videos(episode_id: str, user: dict = Depends(get_current_user)):
    context = Storage.episode_generation_context(user, episode_id)
    if not context:
        not_found("episode")
    shots = context.get("shots", [])
    if not shots:
        not_found("shots")
    data = {"episodes": [context["episode"]], "assets": context.get("assets", [])}
    try:
        provider_tasks = {
            shot["id"]: ai_video.create_video_task(shot.get("visual") or shot["title"], find_reference_image(data, shot), shot["duration"])
            for shot in shots
        }
    except AIError as exc:
        raise ai_error(exc) from exc
    return Storage.batch_create_video_tasks(user, episode_id, provider_tasks, POINT_RULES["video_second"])


@router.get("/projects/{project_id}/assets")
def list_assets(project_id: str, type: str | None = None, user: dict = Depends(get_current_user)):
    return Storage.list_assets(user, project_id, type)


@router.post("/projects/{project_id}/assets")
def create_asset(project_id: str, payload: AssetCreate, user: dict = Depends(get_current_user)):
    refs = normalize_refs(payload.references)
    return Storage.create_asset(user, project_id, payload, refs)


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
    refs = [{
        "id": uid("ref"),
        "type": "image" if visual_asset else "audio",
        "name": f"AI 生成 - {payload.name}",
        "url": generated_url,
        "note": payload.prompt,
    }]
    return Storage.generate_asset(user, project_id, payload, generated_url, refs, visual_asset)


@router.put("/assets/{asset_id}")
def update_asset(asset_id: str, payload: AssetUpdate, user: dict = Depends(get_current_user)):
    return Storage.update_asset(user, asset_id, payload)


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: str, user: dict = Depends(get_current_user)):
    return Storage.delete_asset(user, asset_id)


@router.post("/assets/{asset_id}/voice-clone")
def start_voice_clone(asset_id: str, payload: VoiceCloneRequest, user: dict = Depends(get_current_user)):
    if not payload.consent:
        raise HTTPException(status_code=400, detail="请确认已获得声音授权")
    asset = Storage.get_asset(user, asset_id)
    voice_url = payload.voice_url or asset.get("voice_url")
    if not voice_url or not voice_url.startswith("/uploads/"):
        raise HTTPException(status_code=400, detail="请先上传角色声音样本")
    try:
        audio, _ = storage.get_object(voice_url.removeprefix("/uploads/"))
        speaker_id = asset.get("speaker_id") or f"S_{asset_id.replace('-', '_')}_{uid('voice')[-10:]}"
        result = ai_voice.clone_voice(speaker_id, audio, Path(voice_url).suffix.lstrip(".") or "wav")
    except (AIError, storage.StorageError) as exc:
        raise HTTPException(status_code=503, detail=getattr(exc, "public_message", str(exc))) from exc
    return Storage.update_voice_clone(user, asset_id, result, cost=POINT_RULES["voice_clone"], consume=True, create_job=True)


@router.get("/assets/{asset_id}/voice-clone")
def get_voice_clone(asset_id: str, user: dict = Depends(get_current_user)):
    asset = Storage.get_asset(user, asset_id)
    if not asset.get("speaker_id"):
        return asset
    try:
        result = ai_voice.get_voice(asset["speaker_id"])
    except AIError as exc:
        raise ai_error(exc) from exc
    return Storage.update_voice_clone(user, asset_id, result, cost=0, consume=False, create_job=False)


@router.get("/projects/{project_id}/video-versions")
def list_video_versions(project_id: str, episode_id: str | None = None, user: dict = Depends(get_current_user)):
    return Storage.list_video_versions(user, project_id, episode_id)


@router.delete("/video-versions/{version_id}")
def delete_video_version(version_id: str, user: dict = Depends(get_current_user)):
    return Storage.delete_video_version(user, version_id)


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
    context = Storage.compose_context(user, episode_id)
    if not context:
        not_found("episode")
    shots = context.get("shots", [])
    if not shots or any(shot.get("status") != "completed" for shot in shots):
        raise HTTPException(status_code=400, detail="所有镜头完成后才能合成本集视频")
    shot_order = {shot["id"]: shot["no"] for shot in shots}
    video_url = compose_video_file(sorted(context.get("video_tasks", []), key=lambda item: shot_order.get(item.get("shot_id"), 0)))
    return Storage.save_composed_version(user, episode_id, payload, video_url, POINT_RULES["compose"])


@router.get("/ai-jobs/{job_id}")
def get_ai_job(job_id: str, user: dict = Depends(get_current_user)):
    return Storage.get_ai_job(user, job_id)


@router.get("/projects/{project_id}/ai-jobs")
def list_project_ai_jobs(project_id: str, user: dict = Depends(get_current_user)):
    return Storage.list_project_ai_jobs(user, project_id)


@router.get("/usage")
def usage(user: dict = Depends(get_current_user)):
    return Storage.usage(user)


@router.get("/point-rules")
def point_rules(user: dict = Depends(get_current_user)):
    return POINT_RULES
