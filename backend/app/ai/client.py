from __future__ import annotations

import time
from typing import Any

import httpx

from .errors import (
    AIConfigurationError,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderValidationError,
)

# Module-level client with connection pooling
_client: httpx.Client | None = None
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


def close_client() -> None:
    """Call from FastAPI lifespan shutdown to release connections."""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None


def require_key(value: str, name: str) -> str:
    if not value:
        raise AIConfigurationError(f"{name} is not configured")
    return value


def _should_retry(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    client = _get_client()
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.post(url, headers=headers, json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise AIProviderValidationError("AI provider request failed") from exc

        if response.status_code in {401, 403}:
            raise AIProviderAuthError()
        if _should_retry(response.status_code) and attempt < _MAX_RETRIES - 1:
            retry_after = float(response.headers.get("retry-after", 0))
            delay = max(retry_after, _RETRY_BACKOFF_BASE * (2 ** attempt))
            time.sleep(delay)
            continue
        if response.status_code == 429:
            raise AIProviderRateLimitError()
        if response.status_code >= 400:
            raise AIProviderValidationError(f"AI provider returned {response.status_code}")
        return response.json()
    raise AIProviderRateLimitError()


def get_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    client = _get_client()
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.get(url, headers=headers, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise AIProviderValidationError("AI provider request failed") from exc

        if response.status_code in {401, 403}:
            raise AIProviderAuthError()
        if _should_retry(response.status_code) and attempt < _MAX_RETRIES - 1:
            retry_after = float(response.headers.get("retry-after", 0))
            delay = max(retry_after, _RETRY_BACKOFF_BASE * (2 ** attempt))
            time.sleep(delay)
            continue
        if response.status_code == 429:
            raise AIProviderRateLimitError()
        if response.status_code >= 400:
            raise AIProviderValidationError(f"AI provider returned {response.status_code}")
        return response.json()
    raise AIProviderRateLimitError()
