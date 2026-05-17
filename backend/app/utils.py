"""Shared utility functions used across the application."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


_DT_FORMAT = "%Y-%m-%d %H:%M:%S"


def now() -> str:
    return datetime.now().strftime(_DT_FORMAT)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def fmt_dt(value: Any) -> str:
    """Format a datetime to standard string, passing through empty/None."""
    if isinstance(value, datetime):
        return value.strftime(_DT_FORMAT)
    return value or ""


def parse_dt(value: Any) -> datetime | None:
    """Parse a datetime from string, trying common formats."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for pattern in (_DT_FORMAT, "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value), pattern)
        except ValueError:
            pass
    return None


def public_user_dict(user: Any) -> dict[str, Any]:
    """Build a public-safe user dict from either a dict or ORM User object."""
    if isinstance(user, dict):
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "role": user.get("role", "user"),
            "status": user.get("status", "active"),
            "points": int(user.get("points", 0)),
            "created_at": user.get("created_at", ""),
            "last_login": user.get("last_login", ""),
        }
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "role": user.role or "user",
        "status": user.status or "active",
        "points": int(user.points or 0),
        "created_at": fmt_dt(user.created_at),
        "last_login": fmt_dt(user.last_login_at),
    }


def fix_database_url(url: str) -> str:
    """Convert postgresql:// to postgresql+psycopg:// for SQLAlchemy."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def comparable_asset_names(asset: dict) -> set[str]:
    """Extract comparable name variants from an asset (handles Chinese/English colons)."""
    name = (asset.get("name") or "").strip()
    names = {name}
    if "：" in name:
        names.add(name.rsplit("：", 1)[-1].strip())
    if ":" in name:
        names.add(name.rsplit(":", 1)[-1].strip())
    return {item for item in names if item}


def normalize_refs(refs: list[dict] | None) -> list[dict]:
    """Normalize reference dicts to ensure consistent id/type/name/url/note fields."""
    normalized = []
    for index, ref in enumerate(refs or [], start=1):
        normalized.append({
            "id": ref.get("id") or uid("ref"),
            "type": ref.get("type", "image"),
            "name": ref.get("name") or f"参考 {index:02d}",
            "url": ref.get("url"),
            "note": ref.get("note"),
        })
    return normalized
