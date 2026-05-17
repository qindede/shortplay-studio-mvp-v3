from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from . import queries


def dashboard(user: dict[str, Any]) -> dict[str, Any]:
    return queries.dashboard(user)


def workspace_bootstrap(user: dict[str, Any]) -> dict[str, Any]:
    return queries.workspace_bootstrap(user)


def episode_workspace(user: dict[str, Any], episode_id: str) -> dict[str, Any]:
    result = queries.episode_workspace(user, episode_id)
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result
