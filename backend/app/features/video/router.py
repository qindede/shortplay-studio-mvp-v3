from __future__ import annotations

from fastapi import APIRouter, Depends

from ...schemas import ComposeRequest
from ...security import get_current_user

from . import db, service

router = APIRouter(prefix="/api", tags=["video"])


@router.get("/episodes/{episode_id}/video-jobs")

async def list_video_jobs(episode_id: str, user: dict = Depends(get_current_user)):
    return await service.list_video_jobs_with_poll(user, episode_id)


@router.post("/shots/{shot_id}/generate-video")

async def generate_video_for_shot(shot_id: str, user: dict = Depends(get_current_user)):
    return await service.generate_video_for_shot(user, shot_id)


@router.post("/episodes/{episode_id}/generate-videos")

async def generate_videos_for_episode(episode_id: str, user: dict = Depends(get_current_user)):
    return await service.generate_videos_for_episode(user, episode_id)


@router.get("/projects/{project_id}/video-versions")

async def list_video_versions(project_id: str, episode_id: str | None = None, user: dict = Depends(get_current_user)):
    result = await db.list_video_versions(user, project_id, episode_id)
    if result is None:
        from ..errors import NotFoundError
        raise NotFoundError("项目不存在")
    return result


@router.delete("/video-versions/{version_id}")

async def delete_video_version(version_id: str, user: dict = Depends(get_current_user)):
    if not await db.delete_video_version(user, version_id):
        from ..errors import NotFoundError
        raise NotFoundError("版本不存在")
    return {"ok": True}


@router.post("/episodes/{episode_id}/compose")

async def compose_episode(episode_id: str, payload: ComposeRequest, user: dict = Depends(get_current_user)):
    return await service.compose_episode(user, episode_id, payload, service.compose_video_file)
