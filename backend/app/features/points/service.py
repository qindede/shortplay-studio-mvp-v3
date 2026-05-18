from __future__ import annotations

from typing import Any

from ..errors import InsufficientPointsError
from . import db


async def user_has_points(user_id: str, cost: int) -> bool:
    return await db.user_has_points(user_id, cost)


async def ensure_points(user: dict, cost: int) -> None:
    """Fail before external generation work when the balance is already too low."""
    if cost <= 0:
        return
    if not await db.user_has_points(user["id"], cost):
        raise InsufficientPointsError(f"积分不足：本次需要 {cost}")


def cost_for_shots(shots: list[dict], cost_per_second: int) -> int:
    return sum(max(1, int(shot.get("duration") or 1)) * cost_per_second for shot in shots)


async def point_ledger(user: dict[str, Any], page: int = 1, page_size: int = 10) -> dict[str, Any]:
    return await db.point_ledger(user, page, page_size)


async def usage(user: dict[str, Any]) -> dict[str, Any]:
    return await db.usage(user)
