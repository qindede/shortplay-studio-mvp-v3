from __future__ import annotations

from fastapi import APIRouter, Depends

from ...schemas import AssetCreate, AssetGenerate, AssetUpdate, VoiceCloneRequest
from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["asset"])


@router.get("/projects/{project_id}/assets")

async def list_assets(project_id: str, type: str | None = None, user: dict = Depends(get_current_user)):
    return await service.list_assets(user, project_id, type)


@router.post("/projects/{project_id}/assets")

async def create_asset(project_id: str, payload: AssetCreate, user: dict = Depends(get_current_user)):
    return await service.create_asset(user, project_id, payload)


@router.post("/projects/{project_id}/assets/generate")

async def generate_asset(project_id: str, payload: AssetGenerate, user: dict = Depends(get_current_user)):
    return await service.generate_asset(user, project_id, payload)


@router.put("/assets/{asset_id}")

async def update_asset(asset_id: str, payload: AssetUpdate, user: dict = Depends(get_current_user)):
    return await service.update_asset(user, asset_id, payload)


@router.delete("/assets/{asset_id}")

async def delete_asset(asset_id: str, user: dict = Depends(get_current_user)):
    return await service.delete_asset(user, asset_id)


@router.post("/assets/{asset_id}/voice-clone")

async def start_voice_clone(asset_id: str, payload: VoiceCloneRequest, user: dict = Depends(get_current_user)):
    return await service.start_voice_clone(user, asset_id, payload)


@router.get("/assets/{asset_id}/voice-clone")

async def get_voice_clone(asset_id: str, user: dict = Depends(get_current_user)):
    return await service.get_voice_clone(user, asset_id)
