"""Auth database access. No HTTP exceptions here."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...db import SessionLocal, require_db
from ...models import PointLedger, User
from ...security import verify_password
from ...serializers import _user_dict
from ...utils import parse_dt, public_user_dict, uid


@require_db
def find_user_by_token(token: str | None) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.token == token))
        return _user_dict(user) if user else None


@require_db
def find_user_by_username(username: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        return _user_dict(user) if user else None


@require_db
def get_public_user(user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return public_user_dict(user) if user else None


@require_db
def update_user_login(user_id: str, token: str, last_login: str) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return
        user.token = token
        user.last_login_at = parse_dt(last_login)
        db.commit()


@require_db
def login_user(username: str, password: str, token: str, last_login: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username, User.status == "active"))
        if not user or not verify_password(password, user.password_hash):
            return None
        user.token = token
        user.last_login_at = parse_dt(last_login)
        db.commit()
        db.refresh(user)
        return _user_dict(user)


@require_db
def register_user(
    username: str,
    display_name: str,
    password_hash: str,
    token: str,
    timestamp: str,
    bonus_points: int = 1000,
) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    with SessionLocal() as db:
        user = User(
            id=uid("user"),
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            role="user",
            status="active",
            points=bonus_points,
            token=token,
            usage_json={},
            created_at=ts,
            last_login_at=ts,
        )
        db.add(user)
        db.add(
            PointLedger(
                id=uid("ledger"),
                user_id=user.id,
                amount=bonus_points,
                type="register_bonus",
                scene="注册赠送",
                description="新用户注册赠送积分",
                balance_after=bonus_points,
                created_at=ts,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
        return _user_dict(user)


@require_db
def change_password(user_id: str, current_password: str, new_password: str) -> str:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return "missing"
        if not verify_password(current_password, user.password_hash):
            return "bad_password"
        from ...security import hash_password

        user.password_hash = hash_password(new_password)
        db.commit()
        return "ok"
