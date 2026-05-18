"""AI job database access. No HTTP exceptions here."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from ...db import AsyncSessionLocal
from ...models import AiJob, PointLedger, Project, User
from ...serializers import _ai_job_dict
from ...utils import uid


async def add_ai_job(
    db,
    user_id: str,
    job_type: str,
    provider: str,
    cost: int,
    timestamp: datetime | None,
    status: str = "succeeded",
    progress: int = 100,
    provider_task_id: str | None = None,
    error: str | None = None,
    **links,
) -> AiJob:
    """核心原语：创建 AI 任务记录。调用方需传入 db session。"""
    job = AiJob(
        id=uid("job"),
        user_id=user_id,
        type=job_type,
        provider=provider,
        provider_task_id=provider_task_id,
        status=status,
        progress=progress,
        cost_points=cost,
        input_json={},
        output_json={},
        error=error,
        created_at=timestamp,
        updated_at=timestamp,
        completed_at=timestamp if status in {"succeeded", "failed", "cancelled"} else None,
        **{key: value for key, value in links.items() if value},
    )
    db.add(job)
    return job


async def consume_with_job(
    user_id: str,
    amount: int,
    ledger_scene: str,
    ledger_description: str,
    job_type: str,
    provider: str,
    timestamp: str,
    status: str = "succeeded",
    progress: int = 100,
    provider_task_id: str | None = None,
    **links,
) -> dict[str, Any]:
    from ...utils import parse_dt
    from ..points.db import change_points

    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        try:
            await change_points(db, user_id, -amount, "consume", ledger_scene, ledger_description, ts)
        except ValueError as exc:
            return {"error": str(exc)}
        job = await add_ai_job(db, user_id, job_type, provider, amount, ts, status=status, progress=progress, provider_task_id=provider_task_id, **links)
        await db.commit()
        return {"job": _ai_job_dict(job)}


async def start_paid_ai_job(
    user_id: str,
    amount: int,
    ledger_scene: str,
    ledger_description: str,
    job_type: str,
    provider: str,
    timestamp: str,
    **links,
) -> dict[str, Any]:
    from ...utils import parse_dt
    from ..points.db import change_points

    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        try:
            ledger = await change_points(db, user_id, -amount, "consume", ledger_scene, ledger_description, ts)
        except ValueError as exc:
            return {"error": str(exc)}
        job = await add_ai_job(db, user_id, job_type, provider, amount, ts, status="running", progress=0, **links)
        await db.flush()
        ledger.ai_job_id = job.id
        await db.commit()
        return {"job": _ai_job_dict(job)}


async def complete_ai_job(job_id: str, timestamp: str, output: dict[str, Any] | None = None) -> dict[str, Any] | None:
    from ...utils import parse_dt

    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        job = await db.get(AiJob, job_id)
        if not job:
            return None
        job.status = "succeeded"
        job.progress = 100
        job.error = None
        job.output_json = output or {}
        job.updated_at = ts
        job.completed_at = ts
        await db.commit()
        await db.refresh(job)
        return _ai_job_dict(job)


async def fail_ai_job_with_refund(job_id: str, error: str, timestamp: str) -> dict[str, Any] | None:
    from ...utils import parse_dt

    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        job = await db.get(AiJob, job_id)
        if not job:
            return None
        previous_status = job.status
        job.status = "failed"
        job.progress = 100
        job.error = error
        job.updated_at = ts
        job.completed_at = ts
        cost = int(job.cost_points or 0)
        should_refund = previous_status not in {"failed", "cancelled"} and cost > 0
        if should_refund:
            user = (await db.execute(select(User).where(User.id == job.user_id).with_for_update())).scalar_one_or_none()
            if user:
                user.points = int(user.points or 0) + cost
                db.add(
                    PointLedger(
                        id=uid("ledger"),
                        user_id=job.user_id,
                        amount=cost,
                        type="refund",
                        scene="生成失败退回",
                        description=f"{job.type} 生成失败退回积分",
                        balance_after=user.points,
                        ai_job_id=job.id,
                        created_at=ts,
                    )
                )
        await db.commit()
        await db.refresh(job)
        return _ai_job_dict(job)


async def get_ai_job(user: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        job = await db.get(AiJob, job_id)
        if not job:
            return None
        if job.user_id != user["id"] and user.get("role") != "admin":
            return {"error": "forbidden"}
        return _ai_job_dict(job)


async def list_project_ai_jobs(user: dict[str, Any], project_id: str) -> list[dict[str, Any]] | None:
    async with AsyncSessionLocal() as db:
        owned = (await db.execute(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))).scalar_one_or_none()
        if not owned:
            return None
        jobs = (await db.execute(select(AiJob).where(AiJob.project_id == project_id).order_by(AiJob.created_at.desc()).limit(100))).scalars().all()
        return [_ai_job_dict(job) for job in jobs]
