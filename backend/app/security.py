from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from .config import AUTH_SECRET
from .store import snapshot


def hash_password(password: str) -> str:
    return hashlib.sha256(f"{AUTH_SECRET}:{password}".encode("utf-8")).hexdigest()


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name") or user["username"],
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
        "points": int(user.get("points", 0)),
        "created_at": user.get("created_at", ""),
        "last_login": user.get("last_login", ""),
    }


def find_user_by_token(data: dict, token: str | None) -> dict | None:
    if not token:
        return None
    return next((u for u in data.get("users", []) if u.get("token") == token), None)


def get_current_user(x_user_token: Annotated[str | None, Header(alias="X-User-Token")] = None) -> dict:
    data = snapshot()
    user = find_user_by_token(data, x_user_token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return public_user(user)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
