from __future__ import annotations

from typing import Any

from ..errors import DomainError
from ...utils import uid, now
from . import queries


def list_shots(user: dict[str, Any], episode_id: str) -> list[dict]:
    result = queries.list_shots(user, episode_id)
    if result is None:
        raise DomainError(404, "剧集不存在")
    return result


def create_shot(user: dict[str, Any], episode_id: str, payload: Any) -> dict:
    result = queries.create_shot(user, episode_id, payload, uid("shot"), now())
    if result is None:
        raise DomainError(404, "剧集不存在")
    return result


def patch_shot(user: dict[str, Any], shot_id: str, payload: Any) -> dict:
    result = queries.patch_shot(user, shot_id, payload, now())
    if result is None:
        raise DomainError(404, "镜头不存在")
    return result


def delete_shot(user: dict[str, Any], shot_id: str) -> dict:
    if not queries.delete_shot(user, shot_id, now()):
        raise DomainError(404, "镜头不存在")
    return {"ok": True}
