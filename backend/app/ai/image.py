from __future__ import annotations

from .. import storage
from ..config import AI
from .client import post_json, require_key
from .errors import AIOutputSchemaError


def generate_image(prompt: str) -> str:
    key = require_key(AI.ark_api_key, "ARK_API_KEY")
    body = post_json(
        f"{AI.ark_base_url.rstrip('/')}/images/generations",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        {
            "model": AI.ark_image_model,
            "prompt": prompt,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "size": "2K",
            "stream": False,
            "watermark": False,
        },
        AI.request_timeout,
    )
    image_url = body.get("data", [{}])[0].get("url") or body.get("url")
    if not image_url:
        raise AIOutputSchemaError("Image provider did not return a URL")
    return storage.upload_from_url(image_url, "ai-images")
