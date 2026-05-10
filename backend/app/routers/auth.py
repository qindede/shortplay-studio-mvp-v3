from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import ChangePasswordRequest, LoginRequest, RegisterRequest
from ..security import get_current_user, hash_password, public_user
from ..services import change_points
from ..store import now, snapshot, uid, update

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register")
def register(payload: RegisterRequest):
    username = payload.username.strip().lower()
    display_name = payload.display_name.strip() or username

    def mutate(data):
        if any(u["username"].lower() == username for u in data.get("users", [])):
            raise HTTPException(status_code=409, detail="用户名已存在")

        ts = now()
        user = {
            "id": uid("user"),
            "username": username,
            "display_name": display_name,
            "password_hash": hash_password(payload.password),
            "role": "user",
            "status": "active",
            "points": 0,
            "token": secrets.token_urlsafe(24),
            "created_at": ts,
            "last_login": ts,
        }
        data.setdefault("users", []).append(user)
        change_points(data, user["id"], 1000, "register_bonus", "注册赠送", "新用户注册赠送积分")
        return {"user": public_user(user), "token": user["token"]}

    return update(mutate)


@router.post("/auth/login")
def login(payload: LoginRequest):
    username = payload.username.strip().lower()

    def mutate(data):
        user = next((u for u in data.get("users", []) if u["username"].lower() == username), None)
        if not user or user.get("password_hash") != hash_password(payload.password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if user.get("status") != "active":
            raise HTTPException(status_code=403, detail="账号已被禁用")

        user["token"] = secrets.token_urlsafe(24)
        user["last_login"] = now()
        return {"user": public_user(user), "token": user["token"]}

    return update(mutate)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.patch("/me/password")
def change_my_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    def mutate(data):
        target = next((u for u in data.get("users", []) if u["id"] == user["id"]), None)
        if not target:
            raise HTTPException(status_code=404, detail="用户不存在")
        if target.get("password_hash") != hash_password(payload.current_password):
            raise HTTPException(status_code=400, detail="当前密码不正确")
        target["password_hash"] = hash_password(payload.new_password)
        return {"ok": True}

    return update(mutate)


@router.get("/me/point-ledger")
def my_point_ledger(user: dict = Depends(get_current_user)):
    data = snapshot()
    return [e for e in data.get("point_ledger", []) if e["user_id"] == user["id"]][:100]
