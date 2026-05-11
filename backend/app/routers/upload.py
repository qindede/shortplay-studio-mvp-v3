from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from ..security import get_current_user
from ..store import UPLOAD_DIR

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "audio/mpeg", "audio/wav", "audio/mp3",
}
MAX_SIZE = 10 * 1024 * 1024  # 10MB

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_file(file: UploadFile, user: dict = Depends(get_current_user)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"不支持的文件类型: {file.content_type}")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(400, "文件大小不能超过 10MB")

    ext = Path(file.filename or "file").suffix or ".bin"
    filename = f"{uuid.uuid4().hex[:12]}_{uuid.uuid4().hex[:4]}{ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(data)

    return {"url": f"/uploads/{filename}"}
