from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from ...db import SessionLocal
from ...models import PointLedger, User
from ...utils import uid, fmt_dt


def change_points(
    db,
    user_id: str,
    amount: int,
    kind: str,
    scene: str,
    description: str,
    timestamp: datetime | None,
) -> PointLedger:
    """核心原语：修改用户积分并写入流水。调用方需传入 db session 以保证事务性。"""
    user = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if not user:
        raise ValueError("missing_user")
    current = int(user.points or 0)
    if current + amount < 0:
        raise ValueError("insufficient_points")
    user.points = current + amount
    entry = PointLedger(
        id=uid("ledger"),
        user_id=user_id,
        amount=amount,
        type=kind,
        scene=scene,
        description=description,
        balance_after=user.points,
        created_at=timestamp,
    )
    db.add(entry)
    return entry


def user_has_points(user_id: str, cost: int) -> bool:
    if cost <= 0:
        return True
    with SessionLocal() as db:
        points = db.scalar(select(User.points).where(User.id == user_id))
        return points is not None and int(points or 0) >= cost


def point_ledger(user: dict[str, Any], page: int = 1, page_size: int = 10) -> dict[str, Any]:
    safe_page = max(1, page)
    safe_size = min(100, max(1, page_size))
    offset = (safe_page - 1) * safe_size
    with SessionLocal() as db:
        total = db.scalar(select(func.count(PointLedger.id)).where(PointLedger.user_id == user["id"]))
        rows = db.scalars(
            select(PointLedger)
            .where(PointLedger.user_id == user["id"])
            .order_by(PointLedger.created_at.desc())
            .offset(offset)
            .limit(safe_size)
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "username": user.get("username", ""),
                    "display_name": user.get("display_name", ""),
                    "amount": row.amount,
                    "type": row.type,
                    "scene": row.scene,
                    "description": row.description or "",
                    "balance_after": row.balance_after,
                    "ai_job_id": row.ai_job_id,
                    "created_at": fmt_dt(row.created_at),
                }
                for row in rows
            ],
            "total": total,
        }


def usage(user: dict[str, Any]) -> dict[str, Any]:
    from ...config import apply_usage_defaults

    with SessionLocal() as db:
        db_user = db.get(User, user["id"])
        usage_data = apply_usage_defaults(dict((db_user.usage_json if db_user else user.get("usage")) or {}))
        usage_data["team_members"] = db.scalar(select(func.count(User.id)).where(User.status == "active"))
        return usage_data
