from __future__ import annotations

import functools
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
AsyncSessionLocal = async_sessionmaker(bind=engine, autoflush=False, class_=AsyncSession) if engine else None


def enabled() -> bool:
    return AsyncSessionLocal is not None


def require_db(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if AsyncSessionLocal is None:
            raise RuntimeError("DATABASE_URL is not configured")
        return await func(*args, **kwargs)
    return wrapper


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with AsyncSessionLocal() as session:
        yield session
