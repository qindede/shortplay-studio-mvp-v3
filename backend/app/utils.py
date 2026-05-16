"""Shared utility functions used across the application."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"
