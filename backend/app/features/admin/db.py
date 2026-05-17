"""Admin database access. No HTTP exceptions here."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, text

from ...db import SessionLocal, require_db
from ...models import PointLedger, User
from ...serializers import _ledger_dict
from ...utils import parse_dt, public_user_dict
from ..points.db import change_points


@require_db
def get_user(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        return public_user_dict(user)


@require_db
def admin_summary() -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
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
        ).mappings().one()
        return {key: int(row[key] or 0) for key in row.keys()}


@require_db
def admin_users() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc()))
        return [public_user_dict(user) for user in users]


@require_db
def admin_update_user(user_id: str, role: str | None, status: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        if role is not None:
            user.role = role
        if status is not None:
            user.status = status
        db.commit()
        db.refresh(user)
        return public_user_dict(user)


@require_db
def admin_reset_password(user_id: str, password_hash: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        user.password_hash = password_hash
        user.token = None
        db.commit()
        db.refresh(user)
        return public_user_dict(user)


@require_db
def admin_adjust_points(user_id: str, amount: int, reason: str, timestamp: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return None
        entry = change_points(db, user_id, amount, "admin_adjust", "管理员调整", reason, parse_dt(timestamp))
        db.commit()
        db.refresh(user)
        return {"entry": _ledger_dict(entry, user), "user": public_user_dict(user)}


@require_db
def admin_point_ledger(user_id: str | None = None) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        query = (
            select(PointLedger, User)
            .join(User, User.id == PointLedger.user_id)
            .order_by(PointLedger.created_at.desc())
            .limit(200)
        )
        if user_id:
            query = query.where(PointLedger.user_id == user_id)
        return [_ledger_dict(ledger, user) for ledger, user in db.execute(query).all()]
