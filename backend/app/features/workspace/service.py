from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from . import db


async def dashboard(user: dict[str, Any]) -> dict[str, Any]:
    return await db.dashboard(user)


async def workspace_bootstrap(user: dict[str, Any]) -> dict[str, Any]:
    return await db.workspace_bootstrap(user)


async def episode_workspace(user: dict[str, Any], episode_id: str) -> dict[str, Any]:
    result = await db.episode_workspace(user, episode_id)
    if result is None:
        raise NotFoundError( "剧集不存在")
    return result
