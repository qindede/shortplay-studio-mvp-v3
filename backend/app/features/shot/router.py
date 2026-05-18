from __future__ import annotations

from fastapi import APIRouter, Depends

from ...schemas import ShotCreate, ShotUpdate
from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["shot"])


@router.get("/episodes/{episode_id}/shots")

async def list_shots(episode_id: str, user: dict = Depends(get_current_user)):
    return await service.list_shots(user, episode_id)


@router.post("/episodes/{episode_id}/shots")

async def create_shot(episode_id: str, payload: ShotCreate, user: dict = Depends(get_current_user)):
    return await service.create_shot(user, episode_id, payload)


@router.patch("/shots/{shot_id}")

async def patch_shot(shot_id: str, payload: ShotUpdate, user: dict = Depends(get_current_user)):
    return await service.patch_shot(user, shot_id, payload)


@router.delete("/shots/{shot_id}")

async def delete_shot(shot_id: str, user: dict = Depends(get_current_user)):
    return await service.delete_shot(user, shot_id)
