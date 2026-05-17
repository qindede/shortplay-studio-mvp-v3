from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from ...utils import now
from . import queries


def list_episodes(user: dict[str, Any], project_id: str) -> list[dict]:
    result = queries.list_episodes(user, project_id)
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


def get_episode(user: dict[str, Any], episode_id: str) -> dict:
    result = queries.get_episode(user, episode_id)
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


def create_episode(user: dict[str, Any], project_id: str, payload: Any) -> dict:
    result = queries.create_episode(user, project_id, payload, now())
    if result is None:
        raise NotFoundError( "项目不存在")
    return result


def update_episode(user: dict[str, Any], episode_id: str, payload: Any) -> dict:
    result = queries.update_episode(user, episode_id, payload, now())
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result


def delete_episode(user: dict[str, Any], episode_id: str) -> dict:
    ok, project_id = queries.delete_episode(user, episode_id, now())
    if not ok:
        raise NotFoundError( "剧集不存在")
    return {"ok": True}
