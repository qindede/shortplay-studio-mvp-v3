from __future__ import annotations

from fastapi import APIRouter, Depends

from ...schemas import ProjectCreate, ProjectUpdate
from ...security import get_current_user

from . import service

router = APIRouter(prefix="/api", tags=["project"])


@router.get("/projects")

def list_projects(user: dict = Depends(get_current_user)):
    return service.list_projects(user)


@router.post("/projects")

def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
    return service.create_project(user, payload)


@router.get("/projects/{project_id}")

def get_project(project_id: str, user: dict = Depends(get_current_user)):
    return service.get_project(user, project_id)


@router.put("/projects/{project_id}")

def update_project(project_id: str, payload: ProjectUpdate, user: dict = Depends(get_current_user)):
    return service.update_project(user, project_id, payload)


@router.delete("/projects/{project_id}")

def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    return service.delete_project(user, project_id)
