from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ...utils import uid, now
from . import db


async def list_shots(user: dict[str, Any], episode_id: str) -> list[dict]:
    result = await db.list_shots(user, episode_id)
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


async def create_shot(user: dict[str, Any], episode_id: str, payload: Any) -> dict:
    result = await db.create_shot(user, episode_id, payload, uid("shot"), now())
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


async def patch_shot(user: dict[str, Any], shot_id: str, payload: Any) -> dict:
    result = await db.patch_shot(user, shot_id, payload, now())
    if result is None:
        raise NotFoundError( "镜头不存在")
    return result


async def delete_shot(user: dict[str, Any], shot_id: str) -> dict:
    if not await db.delete_shot(user, shot_id, now()):
        raise NotFoundError( "镜头不存在")
    return {"ok": True}


async def get_generation_context(user: dict[str, Any], shot_id: str) -> dict:
    result = await db.shot_generation_context(user, shot_id)
    if result is None:
        raise NotFoundError("镜头不存在")
    return result
