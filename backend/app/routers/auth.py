from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import ChangePasswordRequest, LoginRequest, RegisterRequest
from ..security import get_current_user, hash_password, public_user
from ..storage_adapter import Storage

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register")
def register(payload: RegisterRequest):
    username = payload.username.strip().lower()
    display_name = payload.display_name.strip() or username
    token = secrets.token_urlsafe(24)
    user = Storage.register_user(username, display_name, hash_password(payload.password), token)
    if user is None:
        raise HTTPException(status_code=409, detail="用户名已存在")
    return {"user": public_user(user), "token": token}


@router.post("/auth/login")
def login(payload: LoginRequest):
    username = payload.username.strip().lower()
    token = secrets.token_urlsafe(24)
    user = Storage.login_user(username, payload.password, token)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return {"user": public_user(user), "token": token}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.patch("/me/password")
def change_my_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    result = Storage.change_password(user["id"], payload.current_password, payload.new_password)
    if result == "missing":
        raise HTTPException(status_code=404, detail="用户不存在")
    if result == "bad_password":
        raise HTTPException(status_code=400, detail="当前密码不正确")
    return {"ok": True}


@router.get("/me/point-ledger")
def my_point_ledger(page: int = 1, page_size: int = 10, user: dict = Depends(get_current_user)):
    return Storage.point_ledger(user, page, page_size)
