"""Admin database access. No HTTP exceptions here."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, text

from ...db import AsyncSessionLocal, require_db
from ...models import PointLedger, User
from ...serializers import _ledger_dict
from ...utils import parse_dt, public_user_dict
from ..points.db import change_points


@require_db
async def get_user(user_id: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return None
        return public_user_dict(user)


@require_db
async def admin_summary() -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text(
                """
                SELECT
                    (SELECT count(*) FROM users) AS user_count,
                    (SELECT count(*) FROM users WHERE status = 'active') AS active_user_count,
                    COALESCE((SELECT sum(points) FROM users), 0) AS total_balance,
                    COALESCE((SELECT -sum(amount) FROM point_ledger WHERE amount < 0), 0) AS consumed_points,
                    COALESCE((SELECT sum(amount) FROM point_ledger WHERE amount > 0), 0) AS granted_points,
                    (SELECT count(*) FROM point_ledger) AS ledger_count
                """
            )
        )).mappings().one()
        return {key: int(row[key] or 0) for key in row.keys()}


@require_db
async def admin_users() -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
        return [public_user_dict(user) for user in users]


@require_db
async def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return None
        if role is not None:
            user.role = role
        if status is not None:
            user.status = status
        await db.commit()
        await db.refresh(user)
        return public_user_dict(user)


@require_db
async def admin_reset_password(user_id: str, password_hash: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return None
        user.password_hash = password_hash
        user.token = None
        await db.commit()
        await db.refresh(user)
        return public_user_dict(user)


@require_db
async def admin_adjust_points(user_id: str, amount: int, reason: str, timestamp: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return None
        entry = await change_points(db, user_id, amount, "admin_adjust", "管理员调整", reason, parse_dt(timestamp))
        await db.commit()
        await db.refresh(user)
        return {"entry": _ledger_dict(entry, user), "user": public_user_dict(user)}


@require_db
async def admin_point_ledger(user_id: str | None = None) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        query = (
            select(PointLedger, User)
            .join(User, User.id == PointLedger.user_id)
            .order_by(PointLedger.created_at.desc())
            .limit(200)
        )
        if user_id:
            query = query.where(PointLedger.user_id == user_id)
        return [_ledger_dict(ledger, user) for ledger, user in (await db.execute(query)).all()]
