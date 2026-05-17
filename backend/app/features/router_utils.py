from __future__ import annotations

import asyncio
import functools

from fastapi import HTTPException

from .errors import (
    BadRequestError,
    ConflictError,
    DomainError,
    ForbiddenError,
    InsufficientPointsError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)

ERROR_STATUS: dict[type[DomainError], int] = {
    BadRequestError: 400,
    UnauthorizedError: 401,
    InsufficientPointsError: 402,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    ServiceUnavailableError: 503,
}


def _resolve_status(exc: DomainError) -> int:
    for exc_class, status in ERROR_STATUS.items():
        if isinstance(exc, exc_class):
            return status
    return 500


def api_endpoint(fn):
    """装饰器：将 service 层的 DomainError 转换为 FastAPI 的 HTTPException。"""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            return fn(*args, **kwargs)
        except DomainError as exc:
            raise HTTPException(status_code=_resolve_status(exc), detail=exc.detail)

    return wrapper
