from __future__ import annotations

from typing import Any

from ..errors import NotFoundError
from . import db


async def get_user(user_id: str) -> dict[str, Any]:
    result = await db.get_user(user_id)
    if result is None:
        raise NotFoundError("用户不存在")
    return result


async def admin_summary() -> dict[str, Any]:
    return await db.admin_summary()


async def admin_users() -> list[dict[str, Any]]:
    return await db.admin_users()


async def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict[str, Any]:
    result = await db.admin_update_user(user_id, role, status)
    if result is None:
        raise NotFoundError("用户不存在")
    return result


async def admin_reset_password(user_id: str, password_hash: str) -> dict[str, Any]:
    result = await db.admin_reset_password(user_id, password_hash)
    if result is None:
        raise NotFoundError("用户不存在")
    return result


async def admin_adjust_points(user_id: str, amount: int, reason: str, timestamp: str) -> dict[str, Any]:
    result = await db.admin_adjust_points(user_id, amount, reason, timestamp)
    if result is None:
        raise NotFoundError("用户不存在")
    return result


async def admin_point_ledger(user_id: str | None = None) -> list[dict[str, Any]]:
    return await db.admin_point_ledger(user_id)
