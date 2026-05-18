from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ...utils import now
from . import db


async def list_projects(user: dict[str, Any]) -> list[dict]:
    return await db.list_projects(user)


async def get_project(user: dict[str, Any], project_id: str) -> dict:
    result = await db.get_project(user, project_id)
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


async def create_project(user: dict[str, Any], payload: Any) -> dict:
    return await db.create_project(user, payload, now())


async def update_project(user: dict[str, Any], project_id: str, payload: Any) -> dict:
    result = await db.update_project(user, project_id, payload, now())
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


async def delete_project(user: dict[str, Any], project_id: str) -> dict:
    ok = await db.delete_project(user, project_id)
    if not ok:
        raise NotFoundError( "项目不存在")
    return {"ok": True}
