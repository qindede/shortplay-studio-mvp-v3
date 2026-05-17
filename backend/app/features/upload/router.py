from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile

from ... import storage
from ...config import UPLOAD_DIR
from ...security import get_current_user
from ..errors import BadRequestError, ServiceUnavailableError
from ..router_utils import api_endpoint

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "audio/mpeg", "audio/wav", "audio/mp3",
}
MAX_SIZE = 10 * 1024 * 1024  # 10MB

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
@api_endpoint
async def upload_file(file: UploadFile, user: dict = Depends(get_current_user)):
    if file.content_type not in ALLOWED_TYPES:
        raise BadRequestError(f"不支持的文件类型: {file.content_type}")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise BadRequestError("文件大小不能超过 10MB")

    try:
        key = storage.make_object_key("uploads", file.filename)
        url = storage.put_bytes(data, key, file.content_type or storage.guess_content_type(file.filename or "file"))
    except storage.StorageError as exc:
        raise ServiceUnavailableError(str(exc)) from exc

    return {"url": url}


@router.get("/uploads/{path:path}")
@api_endpoint
def read_upload(path: str):
    try:
        data, content_type = storage.get_object(path)
    except storage.StorageError as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    return Response(content=data, media_type=content_type)
