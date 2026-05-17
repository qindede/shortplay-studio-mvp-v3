from __future__ import annotations

from typing import Any

from . import queries


def user_has_points(user_id: str, cost: int) -> bool:
    return queries.user_has_points(user_id, cost)


def point_ledger(user: dict[str, Any], page: int = 1, page_size: int = 10) -> dict[str, Any]:
    return queries.point_ledger(user, page, page_size)


def usage(user: dict[str, Any]) -> dict[str, Any]:
    return queries.usage(user)
