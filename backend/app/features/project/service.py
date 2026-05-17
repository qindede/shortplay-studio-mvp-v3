from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ...utils import now
from . import queries


def list_projects(user: dict[str, Any]) -> list[dict]:
    return queries.list_projects(user)


def get_project(user: dict[str, Any], project_id: str) -> dict:
    result = queries.get_project(user, project_id)
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


def create_project(user: dict[str, Any], payload: Any) -> dict:
    return queries.create_project(user, payload, now())


def update_project(user: dict[str, Any], project_id: str, payload: Any) -> dict:
    result = queries.update_project(user, project_id, payload, now())
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


def delete_project(user: dict[str, Any], project_id: str) -> dict:
    ok = queries.delete_project(user, project_id)
    if not ok:
        raise NotFoundError( "项目不存在")
    return {"ok": True}
