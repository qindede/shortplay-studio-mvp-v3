from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas import AdminPointAdjust, AdminUserUpdate
from ..security import public_user, require_admin
from ..services import change_points, user_in_data
from ..store import snapshot, update

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/summary")
def admin_summary(admin: dict = Depends(require_admin)):
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
    data = snapshot()
    return [public_user(u) for u in data.get("users", [])]


@router.patch("/users/{user_id}")
def admin_update_user(user_id: str, payload: AdminUserUpdate, admin: dict = Depends(require_admin)):
    def mutate(data):
        target = user_in_data(data, user_id)
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

    def mutate(data):
        entry = change_points(data, user_id, payload.amount, "admin_adjust", "管理员调整", payload.reason)
        return {"entry": entry, "user": public_user(user_in_data(data, user_id))}

    return update(mutate)


@router.get("/point-ledger")
def admin_point_ledger(user_id: str | None = Query(default=None), admin: dict = Depends(require_admin)):
    data = snapshot()
    rows = data.get("point_ledger", [])
    if user_id:
        rows = [r for r in rows if r["user_id"] == user_id]
    return rows[:200]
