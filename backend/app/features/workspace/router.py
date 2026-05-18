from __future__ import annotations

from fastapi import APIRouter, Depends

from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["workspace"])


@router.get("/dashboard")

async def dashboard(user: dict = Depends(get_current_user)):
    return await service.dashboard(user)


@router.get("/workspace/bootstrap")

async def workspace_bootstrap(user: dict = Depends(get_current_user)):
    return await service.workspace_bootstrap(user)


@router.get("/episodes/{episode_id}/workspace")

async def episode_workspace(episode_id: str, user: dict = Depends(get_current_user)):
    return await service.episode_workspace(user, episode_id)
