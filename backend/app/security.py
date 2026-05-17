from __future__ import annotations

import hashlib
from typing import Annotated

import bcrypt
from fastapi import Depends, Header, HTTPException

from .config import AUTH_SECRET
from .utils import public_user_dict


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2b$") or password_hash.startswith("$2a$"):
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    legacy = hashlib.sha256(f"{AUTH_SECRET}:{password}".encode("utf-8")).hexdigest()
    return legacy == password_hash


def get_current_user(x_user_token: Annotated[str | None, Header(alias="X-User-Token")] = None) -> dict:
    from .storage_adapter import Storage
    user = Storage.find_user_by_token(x_user_token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return public_user_dict(user)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
