from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ...utils import now
from . import db


def list_projects(user: dict[str, Any]) -> list[dict]:
    return db.list_projects(user)


def get_project(user: dict[str, Any], project_id: str) -> dict:
    result = db.get_project(user, project_id)
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


def create_project(user: dict[str, Any], payload: Any) -> dict:
    return db.create_project(user, payload, now())


def update_project(user: dict[str, Any], project_id: str, payload: Any) -> dict:
    result = db.update_project(user, project_id, payload, now())
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


def delete_project(user: dict[str, Any], project_id: str) -> dict:
    ok = db.delete_project(user, project_id)
    if not ok:
        raise NotFoundError( "项目不存在")
    return {"ok": True}
