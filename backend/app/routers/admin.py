from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db_store
from ..schemas import AdminPasswordReset, AdminPointAdjust, AdminUserUpdate
from ..security import hash_password, public_user, require_admin
from ..services import change_points, user_in_data
from ..store import now, snapshot, update

router = APIRouter(prefix="/api/admin", tags=["admin"])
PRIMARY_ADMIN_ID = "user_admin"
PRIMARY_ADMIN_USERNAME = "admin"
DEFAULT_RESET_PASSWORD = "muran123"


def is_primary_admin(user: dict) -> bool:
    return user.get("id") == PRIMARY_ADMIN_ID or user.get("username") == PRIMARY_ADMIN_USERNAME


@router.get("/summary")
def admin_summary(admin: dict = Depends(require_admin)):
    if db_store.enabled():
        return db_store.admin_summary()

    data = snapshot()
    users = data.get("users", [])
    ledger = data.get("point_ledger", [])
    consumed = -sum(e["amount"] for e in ledger if e["amount"] < 0)
    granted = sum(e["amount"] for e in ledger if e["amount"] > 0)
    return {
        "user_count": len(users),
        "active_user_count": len([u for u in users if u.get("status") == "active"]),
        "total_balance": sum(int(u.get("points", 0)) for u in users),
        "consumed_points": consumed,
        "granted_points": granted,
        "ledger_count": len(ledger),
    }


@router.get("/users")
def admin_users(admin: dict = Depends(require_admin)):
    if db_store.enabled():
        return db_store.admin_users()

    data = snapshot()
    return [public_user(u) for u in data.get("users", [])]


@router.patch("/users/{user_id}")
def admin_update_user(user_id: str, payload: AdminUserUpdate, admin: dict = Depends(require_admin)):
    if db_store.enabled():
        target = db_store.find_user_by_username(admin["username"]) if user_id == admin["id"] else None
        target = target or (db_store.find_user_by_token(admin.get("token")) if False else None)
        users = db_store.admin_users()
        target = next((item for item in users if item["id"] == user_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="user not found")
        is_self_update = target["id"] == admin["id"]
        is_primary_update = is_primary_admin(target)
        if is_self_update and payload.status == "disabled":
            raise HTTPException(status_code=400, detail="不能禁用当前登录的管理员账号")
        if is_self_update and payload.role == "user":
            raise HTTPException(status_code=400, detail="不能移除当前登录账号的管理员角色")
        if payload.role == "admin" and not is_primary_admin(admin):
            raise HTTPException(status_code=403, detail="只有主管理员可以添加子管理员")
        if is_primary_update and payload.status == "disabled":
            raise HTTPException(status_code=400, detail="不能禁用主管理员账号")
        if is_primary_update and payload.role == "user":
            raise HTTPException(status_code=400, detail="不能修改主管理员角色")
        updated = db_store.admin_update_user(user_id, payload.role, payload.status)
        if not updated:
            raise HTTPException(status_code=404, detail="user not found")
        return updated

    def mutate(data):
        target = user_in_data(data, user_id)
        is_self_update = target["id"] == admin["id"]
        is_primary_update = is_primary_admin(target)
        if is_self_update and payload.status == "disabled":
            raise HTTPException(status_code=400, detail="不能禁用当前登录的管理员账号")
        if is_self_update and payload.role == "user":
            raise HTTPException(status_code=400, detail="不能移除当前登录账号的管理员角色")
        if payload.role == "admin" and not is_primary_admin(admin):
            raise HTTPException(status_code=403, detail="只有主管理员可以添加子管理员")
        if is_primary_update and payload.status == "disabled":
            raise HTTPException(status_code=400, detail="不能禁用主管理员账号")
        if is_primary_update and payload.role == "user":
            raise HTTPException(status_code=400, detail="不能修改主管理员角色")
        if payload.role is not None:
            target["role"] = payload.role
        if payload.status is not None:
            target["status"] = payload.status
        return public_user(target)

    return update(mutate)


@router.post("/users/{user_id}/points")
def admin_adjust_points(user_id: str, payload: AdminPointAdjust, admin: dict = Depends(require_admin)):
    if payload.amount == 0:
        raise HTTPException(status_code=400, detail="调整积分不能为 0")

    if db_store.enabled():
        result = db_store.admin_adjust_points(user_id, payload.amount, payload.reason, now())
        if result is None:
            raise HTTPException(status_code=404, detail="user not found")
        return result

    def mutate(data):
        entry = change_points(data, user_id, payload.amount, "admin_adjust", "管理员调整", payload.reason)
        return {"entry": entry, "user": public_user(user_in_data(data, user_id))}

    return update(mutate)


@router.patch("/users/{user_id}/password")
def admin_reset_user_password(user_id: str, payload: AdminPasswordReset, admin: dict = Depends(require_admin)):
    if db_store.enabled():
        users = db_store.admin_users()
        target = next((item for item in users if item["id"] == user_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="user not found")
        if target["id"] == admin["id"]:
            raise HTTPException(status_code=400, detail="请在账号设置中修改自己的密码")
        if is_primary_admin(target):
            raise HTTPException(status_code=400, detail="不能重置主管理员密码")
        updated = db_store.admin_reset_password(user_id, hash_password(payload.password))
        return {"user": updated}

    def mutate(data):
        target = user_in_data(data, user_id)
        if target["id"] == admin["id"]:
            raise HTTPException(status_code=400, detail="请在账号设置中修改自己的密码")
        if is_primary_admin(target):
            raise HTTPException(status_code=400, detail="不能重置主管理员密码")
        target["password_hash"] = hash_password(DEFAULT_RESET_PASSWORD)
        target["token"] = ""
        return {"user": public_user(target)}

    return update(mutate)


@router.get("/point-ledger")
def admin_point_ledger(user_id: str | None = Query(default=None), admin: dict = Depends(require_admin)):
    if db_store.enabled():
        return db_store.admin_point_ledger(user_id)

    data = snapshot()
    rows = data.get("point_ledger", [])
    if user_id:
        rows = [r for r in rows if r["user_id"] == user_id]
    return rows[:200]
