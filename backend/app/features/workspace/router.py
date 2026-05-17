from __future__ import annotations

from fastapi import APIRouter, Depends

from ...security import get_current_user
from ..router_utils import api_endpoint
from . import service

router = APIRouter(prefix="/api", tags=["workspace"])


@router.get("/dashboard")
@api_endpoint
def dashboard(user: dict = Depends(get_current_user)):
    return service.dashboard(user)


@router.get("/workspace/bootstrap")
@api_endpoint
def workspace_bootstrap(user: dict = Depends(get_current_user)):
    return service.workspace_bootstrap(user)


@router.get("/episodes/{episode_id}/workspace")
@api_endpoint
def episode_workspace(episode_id: str, user: dict = Depends(get_current_user)):
    return service.episode_workspace(user, episode_id)
