from __future__ import annotations

from fastapi import APIRouter, Depends

from ...schemas import EpisodeCreate, EpisodeUpdate
from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["episode"])


@router.get("/projects/{project_id}/episodes")

async def list_episodes(project_id: str, user: dict = Depends(get_current_user)):
    return await service.list_episodes(user, project_id)


@router.post("/projects/{project_id}/episodes")

async def create_episode(project_id: str, payload: EpisodeCreate, user: dict = Depends(get_current_user)):
    return await service.create_episode(user, project_id, payload)


@router.get("/episodes/{episode_id}")

async def get_episode(episode_id: str, user: dict = Depends(get_current_user)):
    return await service.get_episode(user, episode_id)


@router.put("/episodes/{episode_id}")

async def update_episode(episode_id: str, payload: EpisodeUpdate, user: dict = Depends(get_current_user)):
    return await service.update_episode(user, episode_id, payload)


@router.delete("/episodes/{episode_id}")

async def delete_episode(episode_id: str, user: dict = Depends(get_current_user)):
    return await service.delete_episode(user, episode_id)
