"""Storyboard feature — API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...schemas import (
    OutlineGenerateRequest,
    OutlineGenerateResponse,
    PromptOptimizeRequest,
    StoryboardGenerateRequest,
    StoryboardPrepareResponse,
)
from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["storyboard"])


@router.post("/projects/generate-outline", response_model=OutlineGenerateResponse)

async def generate_project_outline(payload: OutlineGenerateRequest, user: dict = Depends(get_current_user)):
    return await service.generate_project_outline(user, payload)


@router.post("/episodes/{episode_id}/prepare-storyboard", response_model=StoryboardPrepareResponse)

async def prepare_storyboard(episode_id: str, user: dict = Depends(get_current_user)):
    return await service.prepare_storyboard(user, episode_id)


@router.post("/episodes/{episode_id}/generate-storyboard")

async def generate_storyboard(episode_id: str, payload: StoryboardGenerateRequest | None = None, user: dict = Depends(get_current_user)):
    return await service.generate_storyboard(user, episode_id, payload)


@router.post("/optimize-prompt")

async def optimize_prompt_endpoint(payload: PromptOptimizeRequest, user: dict = Depends(get_current_user)):
    return await service.optimize_prompt(payload.prompt, payload.context, payload.project_name)
