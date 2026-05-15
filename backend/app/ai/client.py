from __future__ import annotations

from typing import Any

import httpx

from .errors import (
    AIConfigurationError,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderValidationError,
)


def require_key(value: str, name: str) -> str:
    if not value:
        raise AIConfigurationError(f"{name} is not configured")
    return value


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise AIProviderTimeoutError() from exc
    except httpx.HTTPError as exc:
        raise AIProviderValidationError("AI provider request failed") from exc

    if response.status_code in {401, 403}:
        raise AIProviderAuthError()
    if response.status_code == 429:
        raise AIProviderRateLimitError()
    if response.status_code >= 400:
        raise AIProviderValidationError(f"AI provider returned {response.status_code}")
    return response.json()


def get_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise AIProviderTimeoutError() from exc
    except httpx.HTTPError as exc:
        raise AIProviderValidationError("AI provider request failed") from exc

    if response.status_code in {401, 403}:
        raise AIProviderAuthError()
    if response.status_code == 429:
        raise AIProviderRateLimitError()
    if response.status_code >= 400:
        raise AIProviderValidationError(f"AI provider returned {response.status_code}")
    return response.json()
