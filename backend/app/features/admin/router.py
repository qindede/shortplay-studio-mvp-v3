from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...schemas import AdminPasswordReset, AdminPointAdjust, AdminUserUpdate
from ...security import get_current_user, hash_password, require_admin
from ...utils import now
from ..errors import BadRequestError, ForbiddenError
from ..router_utils import api_endpoint
from . import service

router = APIRouter(prefix="/api/admin", tags=["admin"])

PRIMARY_ADMIN_ID = "user_admin"
PRIMARY_ADMIN_USERNAME = "admin"


def is_primary_admin(user: dict) -> bool:
    return user.get("id") == PRIMARY_ADMIN_ID or user.get("username") == PRIMARY_ADMIN_USERNAME


@router.get("/summary")
@api_endpoint
def admin_summary(admin: dict = Depends(require_admin)):
    return service.admin_summary()


@router.get("/users")
@api_endpoint
def admin_users(admin: dict = Depends(require_admin)):
    return service.admin_users()


@router.patch("/users/{user_id}")
@api_endpoint
def admin_update_user(user_id: str, payload: AdminUserUpdate, admin: dict = Depends(require_admin)):
    target = service.get_user(user_id)
    is_self_update = target["id"] == admin["id"]
    is_primary = is_primary_admin(target)
    if is_self_update and payload.status == "disabled":
        raise BadRequestError("不能禁用当前登录的管理员账号")
    if is_self_update and payload.role == "user":
        raise BadRequestError("不能移除当前登录账号的管理员角色")
    if payload.role == "admin" and not is_primary_admin(admin):
        raise ForbiddenError("只有主管理员可以添加子管理员")
    if is_primary and payload.status == "disabled":
        raise BadRequestError("不能禁用主管理员账号")
    if is_primary and payload.role == "user":
        raise BadRequestError("不能修改主管理员角色")
    return service.admin_update_user(user_id, payload.role, payload.status)


@router.post("/users/{user_id}/reset-password")
@api_endpoint
def admin_reset_user_password(user_id: str, payload: AdminPasswordReset, admin: dict = Depends(require_admin)):
    target = service.get_user(user_id)
    if target["id"] == admin["id"]:
        raise BadRequestError("请在账号设置中修改自己的密码")
    if is_primary_admin(target):
        raise BadRequestError("不能重置主管理员密码")
    return {"user": service.admin_reset_password(user_id, hash_password(payload.password))}


@router.post("/users/{user_id}/adjust-points")
@api_endpoint
def admin_adjust_points(user_id: str, payload: AdminPointAdjust, admin: dict = Depends(require_admin)):
    if payload.amount == 0:
        raise BadRequestError("调整积分不能为 0")
    return service.admin_adjust_points(user_id, payload.amount, payload.reason, now())


@router.get("/point-ledger")
@api_endpoint
def admin_point_ledger(user_id: str | None = Query(default=None), admin: dict = Depends(require_admin)):
    return service.admin_point_ledger(user_id)
