from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ...utils import now
from . import db


async def list_episodes(user: dict[str, Any], project_id: str) -> list[dict]:
    result = await db.list_episodes(user, project_id)
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


async def get_episode(user: dict[str, Any], episode_id: str) -> dict:
    result = await db.get_episode(user, episode_id)
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


async def create_episode(user: dict[str, Any], project_id: str, payload: Any) -> dict:
    result = await db.create_episode(user, project_id, payload, now())
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


async def update_episode(user: dict[str, Any], episode_id: str, payload: Any) -> dict:
    result = await db.update_episode(user, episode_id, payload, now())
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


async def delete_episode(user: dict[str, Any], episode_id: str) -> dict:
    ok, project_id = await db.delete_episode(user, episode_id, now())
    if not ok:
        raise NotFoundError( "剧集不存在")
    return {"ok": True}
