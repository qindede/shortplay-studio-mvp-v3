from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ...utils import uid, now
from . import db


def list_shots(user: dict[str, Any], episode_id: str) -> list[dict]:
    result = db.list_shots(user, episode_id)
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


def create_shot(user: dict[str, Any], episode_id: str, payload: Any) -> dict:
    result = db.create_shot(user, episode_id, payload, uid("shot"), now())
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


def patch_shot(user: dict[str, Any], shot_id: str, payload: Any) -> dict:
    result = db.patch_shot(user, shot_id, payload, now())
    if result is None:
        raise NotFoundError( "镜头不存在")
    return result


def delete_shot(user: dict[str, Any], shot_id: str) -> dict:
    if not db.delete_shot(user, shot_id, now()):
        raise NotFoundError( "镜头不存在")
    return {"ok": True}


def get_generation_context(user: dict[str, Any], shot_id: str) -> dict:
    result = db.shot_generation_context(user, shot_id)
    if result is None:
        raise NotFoundError("镜头不存在")
    return result
