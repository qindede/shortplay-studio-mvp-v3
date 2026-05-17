from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends

from ...schemas import ChangePasswordRequest, LoginRequest, RegisterRequest
from ...security import get_current_user, hash_password, public_user
from ...utils import now
from ..points import service as points_service
from ..router_utils import api_endpoint
from . import service

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register")
@api_endpoint
def register(payload: RegisterRequest):
    username = payload.username.strip().lower()
    display_name = payload.display_name.strip() or username
    token = secrets.token_urlsafe(24)
    user = service.register_user(username, display_name, hash_password(payload.password), token, now())
    return {"user": public_user(user), "token": token}


@router.post("/auth/login")
@api_endpoint
def login(payload: LoginRequest):
    username = payload.username.strip().lower()
    token = secrets.token_urlsafe(24)
    user = service.login_user(username, payload.password, token, now())
    return {"user": public_user(user), "token": token}


@router.get("/me")
@api_endpoint
def me(user: dict = Depends(get_current_user)):
    return user


@router.patch("/me/password")
@api_endpoint
def change_my_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    service.change_password(user["id"], payload.current_password, payload.new_password)
    return {"ok": True}


@router.get("/me/point-ledger")
@api_endpoint
def my_point_ledger(page: int = 1, page_size: int = 10, user: dict = Depends(get_current_user)):
    return points_service.point_ledger(user, page, page_size)
