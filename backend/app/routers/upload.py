from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile

from ..security import get_current_user
from .. import storage
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

    try:
        key = storage.make_object_key("uploads", file.filename)
        url = storage.put_bytes(data, key, file.content_type or storage.guess_content_type(file.filename or "file"))
    except storage.StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"url": url}


@router.get("/uploads/{path:path}")
def read_upload(path: str):
    try:
        data, content_type = storage.get_object(path)
    except storage.StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=data, media_type=content_type)
