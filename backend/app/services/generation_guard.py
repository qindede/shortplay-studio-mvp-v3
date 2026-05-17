from __future__ import annotations

from fastapi import HTTPException

from ..storage_adapter import Storage


def ensure_points(user: dict, cost: int) -> None:
    """Fail before external generation work when the balance is already too low."""
    if cost <= 0:
        return
    if not Storage.user_has_points(user["id"], cost):
        raise HTTPException(status_code=402, detail=f"积分不足：本次需要 {cost}")


def cost_for_shots(shots: list[dict], cost_per_second: int) -> int:
    return sum(max(1, int(shot.get("duration") or 1)) * cost_per_second for shot in shots)
