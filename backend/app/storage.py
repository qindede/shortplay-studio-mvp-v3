from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from urllib.parse import quote, unquote

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from .config import R2


class StorageError(RuntimeError):
    pass


def configured() -> bool:
    return bool(R2.endpoint_url and R2.access_key_id and R2.secret_access_key and R2.bucket)


def client():
    if not configured():
        raise StorageError("R2 object storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=R2.endpoint_url,
        aws_access_key_id=R2.access_key_id,
        aws_secret_access_key=R2.secret_access_key,
        region_name="auto",
    )


def normalize_key(key: str) -> str:
    key = unquote(key).lstrip("/")
    prefix = R2.prefix.strip("/")
    if prefix and not key.startswith(prefix + "/"):
        key = f"{prefix}/{key}"
    return key


def public_path(key: str) -> str:
    return f"/uploads/{quote(normalize_key(key), safe='/')}"


def guess_content_type(name: str, fallback: str = "application/octet-stream") -> str:
    return mimetypes.guess_type(name)[0] or fallback


def make_object_key(category: str, filename: str | None, suffix: str | None = None) -> str:
    ext = suffix or Path(filename or "file").suffix or ".bin"
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    return normalize_key(f"{category}/{uuid.uuid4().hex}{safe_ext}")


def put_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    try:
        client().put_object(Bucket=R2.bucket, Key=normalize_key(key), Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError) as exc:
        raise StorageError("Failed to upload file to R2") from exc
    return public_path(key)


def get_object(key: str) -> tuple[bytes, str]:
    try:
        response = client().get_object(Bucket=R2.bucket, Key=normalize_key(key))
        body = response["Body"].read()
        content_type = response.get("ContentType") or guess_content_type(key)
        return body, content_type
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404"}:
            raise HTTPException(status_code=404, detail="文件不存在") from exc
        raise StorageError("Failed to read file from R2") from exc
    except BotoCoreError as exc:
        raise StorageError("Failed to read file from R2") from exc


def upload_from_url(url: str, category: str, suffix: str | None = None) -> str:
    try:
        with httpx.Client(timeout=60) as http:
            response = http.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise StorageError("Failed to download provider file") from exc

    content_type = response.headers.get("content-type") or guess_content_type(url)
    ext = suffix or mimetypes.guess_extension(content_type) or Path(url.split("?")[0]).suffix or ".bin"
    key = make_object_key(category, url, ext)
    return put_bytes(response.content, key, content_type)
