from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from ...ai.errors import AIError
from ... import storage
from ...utils import now
from ..errors import ForbiddenError, InsufficientPointsError, NotFoundError
from . import db

T = TypeVar("T")


async def start_paid_ai_job(user: dict, cost: int, scene: str, description: str, job_type: str, provider: str, **links) -> dict:
    result = await db.start_paid_ai_job(user["id"], cost, scene, description, job_type, provider, now(), **links)
    if result.get("error") == "insufficient_points":
        raise InsufficientPointsError(f"积分不足：本次需要 {cost}")
    return result["job"]


async def complete_ai_job(job_id: str, output: dict | None = None) -> dict:
    job = await db.complete_ai_job(job_id, now(), output)
    if not job:
        raise NotFoundError("AI 任务不存在")
    return job


async def fail_ai_job_with_refund(job_id: str, error: str) -> dict:
    job = await db.fail_ai_job_with_refund(job_id, error, now())
    if not job:
        raise NotFoundError("AI 任务不存在")
    return job


async def get_ai_job(user: dict, job_id: str) -> dict:
    job = await db.get_ai_job(user, job_id)
    if not job:
        raise NotFoundError("AI 任务不存在")
    if job.get("error") == "forbidden":
        raise ForbiddenError("无权访问该任务")
    return job


async def list_project_ai_jobs(user: dict, project_id: str) -> list[dict]:
    jobs = await db.list_project_ai_jobs(user, project_id)
    if jobs is None:
        raise NotFoundError("项目不存在")
    return jobs


async def run_paid_generation(
    user: dict,
    cost: int,
    scene: str,
    description: str,
    job_type: str,
    provider: str,
    work: Callable[[dict], tuple[T, dict[str, Any] | None]],
    failure_message: str = "生成失败",
    complete: bool = True,
    **links,
) -> T:
    job = await start_paid_ai_job(user, cost, scene, description, job_type, provider, **links)
    try:
        result, output = await work(job)
    except AIError as exc:
        await fail_ai_job_with_refund(job["id"], exc.public_message)
        raise
    except storage.StorageError as exc:
        await fail_ai_job_with_refund(job["id"], str(exc))
        raise
    except Exception as exc:
        await fail_ai_job_with_refund(job["id"], str(exc) or failure_message)
        raise
    if complete:
        await complete_ai_job(job["id"], output or {})
    return result
