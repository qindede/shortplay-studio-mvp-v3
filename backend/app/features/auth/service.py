from __future__ import annotations

from typing import Any

from ..errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from . import queries


def login_user(username: str, password: str, token: str, last_login: str) -> dict[str, Any]:
    user = queries.login_user(username, password, token, last_login)
    if not user:
        raise UnauthorizedError("用户名或密码错误")
    if user.get("status") != "active":
        raise ForbiddenError("账号已被禁用")
    return user


def register_user(
    username: str,
    display_name: str,
    password_hash: str,
    token: str,
    timestamp: str,
    bonus_points: int = 1000,
) -> dict[str, Any]:
    user = queries.register_user(username, display_name, password_hash, token, timestamp, bonus_points)
    if user is None:
        raise ConflictError("用户名已存在")
    return user


def change_password(user_id: str, current_password: str, new_password: str) -> None:
    result = queries.change_password(user_id, current_password, new_password)
    if result == "missing":
        raise NotFoundError("用户不存在")
    if result == "bad_password":
        raise BadRequestError("当前密码不正确")


def get_current_user(token: str | None) -> dict[str, Any]:
    user = queries.find_user_by_token(token)
    if not user:
        raise UnauthorizedError("未登录或登录已失效")
    if user.get("status") != "active":
        raise ForbiddenError("账号已被禁用")
    return user
