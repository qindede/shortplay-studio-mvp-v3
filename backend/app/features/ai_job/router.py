from __future__ import annotations

from fastapi import APIRouter, Depends

from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["ai-job"])


@router.get("/ai-jobs/{job_id}")

async def get_ai_job(job_id: str, user: dict = Depends(get_current_user)):
    return await service.get_ai_job(user, job_id)


@router.get("/projects/{project_id}/ai-jobs")

async def list_project_ai_jobs(project_id: str, user: dict = Depends(get_current_user)):
    return await service.list_project_ai_jobs(user, project_id)
