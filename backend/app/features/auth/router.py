from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends

from ...schemas import ChangePasswordRequest, LoginRequest, RegisterRequest
from ...security import get_current_user, hash_password, public_user
from ...utils import now
from ..points import service as points_service

from . import service

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register")

async def register(payload: RegisterRequest):
    username = payload.username.strip().lower()
    display_name = payload.display_name.strip() or username
    token = secrets.token_urlsafe(24)
    user = await service.register_user(username, display_name, hash_password(payload.password), token, now())
    return {"user": public_user(user), "token": token}


@router.post("/auth/login")

async def login(payload: LoginRequest):
    username = payload.username.strip().lower()
    token = secrets.token_urlsafe(24)
    user = await service.login_user(username, payload.password, token, now())
    return {"user": public_user(user), "token": token}


@router.get("/me")

async def me(user: dict = Depends(get_current_user)):
    return user


@router.patch("/me/password")

async def change_my_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    await service.change_password(user["id"], payload.current_password, payload.new_password)
    return {"ok": True}


@router.get("/me/point-ledger")

async def my_point_ledger(page: int = 1, page_size: int = 10, user: dict = Depends(get_current_user)):
    return await points_service.point_ledger(user, page, page_size)
