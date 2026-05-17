from __future__ import annotations

from fastapi import APIRouter, Depends

from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["workspace"])


@router.get("/dashboard")

def dashboard(user: dict = Depends(get_current_user)):
    return service.dashboard(user)


@router.get("/workspace/bootstrap")

def workspace_bootstrap(user: dict = Depends(get_current_user)):
    return service.workspace_bootstrap(user)


@router.get("/episodes/{episode_id}/workspace")

def episode_workspace(episode_id: str, user: dict = Depends(get_current_user)):
    return service.episode_workspace(user, episode_id)
