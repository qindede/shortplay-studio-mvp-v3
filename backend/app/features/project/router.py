from __future__ import annotations

from fastapi import APIRouter, Depends

from ...security import get_current_user
from ..router_utils import api_endpoint
from . import service

router = APIRouter(prefix="/api", tags=["project"])


@router.get("/projects")
@api_endpoint
def list_projects(user: dict = Depends(get_current_user)):
    return service.list_projects(user)


@router.post("/projects")
@api_endpoint
def create_project(payload, user: dict = Depends(get_current_user)):
    return service.create_project(user, payload)


@router.get("/projects/{project_id}")
@api_endpoint
def get_project(project_id: str, user: dict = Depends(get_current_user)):
    return service.get_project(user, project_id)


@router.put("/projects/{project_id}")
@api_endpoint
def update_project(project_id: str, payload, user: dict = Depends(get_current_user)):
    return service.update_project(user, project_id, payload)


@router.delete("/projects/{project_id}")
@api_endpoint
def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    return service.delete_project(user, project_id)
