from __future__ import annotations

import asyncio
import functools

from fastapi import HTTPException

from .errors import DomainError


def api_endpoint(fn):
    """装饰器：将 service 层的 DomainError 转换为 FastAPI 的 HTTPException。"""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            return fn(*args, **kwargs)
        except DomainError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return wrapper
