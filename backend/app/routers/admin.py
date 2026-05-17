from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas import AdminPasswordReset, AdminPointAdjust, AdminUserUpdate
from ..security import hash_password, require_admin
from ..storage_adapter import Storage

router = APIRouter(prefix="/api/admin", tags=["admin"])
PRIMARY_ADMIN_ID = "user_admin"
PRIMARY_ADMIN_USERNAME = "admin"


def is_primary_admin(user: dict) -> bool:
    return user.get("id") == PRIMARY_ADMIN_ID or user.get("username") == PRIMARY_ADMIN_USERNAME


@router.get("/summary")
def admin_summary(admin: dict = Depends(require_admin)):
    return Storage.admin_summary()


@router.get("/users")
def admin_users(admin: dict = Depends(require_admin)):
    return Storage.admin_users()


@router.patch("/users/{user_id}")
def admin_update_user(user_id: str, payload: AdminUserUpdate, admin: dict = Depends(require_admin)):
    target = Storage.admin_user(user_id)
    is_self_update = target["id"] == admin["id"]
    is_primary = is_primary_admin(target)
    if is_self_update and payload.status == "disabled":
        raise HTTPException(status_code=400, detail="不能禁用当前登录的管理员账号")
    if is_self_update and payload.role == "user":
        raise HTTPException(status_code=400, detail="不能移除当前登录账号的管理员角色")
    if payload.role == "admin" and not is_primary_admin(admin):
        raise HTTPException(status_code=403, detail="只有主管理员可以添加子管理员")
    if is_primary and payload.status == "disabled":
        raise HTTPException(status_code=400, detail="不能禁用主管理员账号")
    if is_primary and payload.role == "user":
        raise HTTPException(status_code=400, detail="不能修改主管理员角色")
    updated = Storage.admin_update_user(user_id, payload.role, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="user not found")
    return updated


@router.post("/users/{user_id}/points")
def admin_adjust_points(user_id: str, payload: AdminPointAdjust, admin: dict = Depends(require_admin)):
    if payload.amount == 0:
        raise HTTPException(status_code=400, detail="调整积分不能为 0")
    result = Storage.admin_adjust_points(user_id, payload.amount, payload.reason)
    if result is None:
        raise HTTPException(status_code=404, detail="user not found")
    return result


@router.patch("/users/{user_id}/password")
def admin_reset_user_password(user_id: str, payload: AdminPasswordReset, admin: dict = Depends(require_admin)):
    target = Storage.admin_user(user_id)
    if target["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="请在账号设置中修改自己的密码")
    if is_primary_admin(target):
        raise HTTPException(status_code=400, detail="不能重置主管理员密码")
    updated = Storage.admin_reset_password(user_id, hash_password(payload.password))
    return {"user": updated}


@router.get("/point-ledger")
def admin_point_ledger(user_id: str | None = Query(default=None), admin: dict = Depends(require_admin)):
    return Storage.admin_point_ledger(user_id)
