from __future__ import annotations

import base64
import uuid

from .. import storage
from ..config import AI
from .client import post_json, require_key


VOICE_CLONE_URL = "https://openspeech.bytedance.com/api/v3/tts/voice_clone"
GET_VOICE_URL = "https://openspeech.bytedance.com/api/v3/tts/get_voice"


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Api-Key": require_key(AI.volc_voice_api_key, "VOLC_VOICE_API_KEY"),
        "X-Api-Request-Id": str(uuid.uuid4()),
    }


def clone_voice(speaker_id: str, audio: bytes, audio_format: str = "wav") -> dict:
    body = post_json(
        VOICE_CLONE_URL,
        _headers(),
        {
            "speaker_id": speaker_id,
            "audio": {"data": base64.b64encode(audio).decode("ascii"), "format": audio_format},
            "language": 0,
            "extra_params": {"voice_clone_denoise_model_id": ""},
        },
        AI.request_timeout,
    )
    return normalize_voice_response(body)


def get_voice(speaker_id: str) -> dict:
    return normalize_voice_response(post_json(GET_VOICE_URL, _headers(), {"speaker_id": speaker_id}, AI.request_timeout))


def normalize_voice_response(body: dict) -> dict:
    status_code = int(body.get("status", 0))
    status = "pending"
    if status_code in {1}:
        status = "generating"
    elif status_code in {2, 4}:
        status = "completed"
    elif status_code in {3}:
        status = "failed"

    demo_url = None
    for item in body.get("speaker_status", []) or []:
        if item.get("demo_audio"):
            demo_url = storage.upload_from_url(item["demo_audio"], "voices")
            break

    return {
        "speaker_id": body.get("speaker_id"),
        "voice_status": status,
        "voice_url": demo_url,
        "error": body.get("message") if status == "failed" else None,
    }
