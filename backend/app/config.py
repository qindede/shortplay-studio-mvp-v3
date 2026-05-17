from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .utils import fix_database_url

load_dotenv()

AUTH_SECRET = os.getenv("SHORTPLAY_AUTH_SECRET", "shortplay-mvp-secret")
DATABASE_URL = fix_database_url(os.getenv("DATABASE_URL", ""))
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "")
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class AISettings:
    minimax_base_url: str = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    minimax_api_key: str = os.getenv("MINIMAX_API_KEY", "")
    minimax_text_model: str = os.getenv("MINIMAX_TEXT_MODEL", "MiniMax-Text-01")
    ark_base_url: str = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    ark_api_key: str = os.getenv("ARK_API_KEY", "")
    ark_image_model: str = os.getenv("ARK_IMAGE_MODEL", "doubao-seedream-5-0-260128")
    ark_video_model: str = os.getenv("ARK_VIDEO_MODEL", "doubao-seedance-1-0-pro-fast-251015")
    volc_voice_api_key: str = os.getenv("VOLC_VOICE_API_KEY", "")
    request_timeout: float = float(os.getenv("AI_REQUEST_TIMEOUT", "120"))
    generation_timeout: float = float(os.getenv("AI_GENERATION_TIMEOUT", "300"))


@dataclass(frozen=True)
class R2Settings:
    account_id: str = os.getenv("R2_ACCOUNT_ID", "")
    endpoint_url: str = os.getenv("R2_ENDPOINT_URL", "")
    access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    bucket: str = os.getenv("R2_BUCKET", "muran")
    prefix: str = os.getenv("R2_PREFIX", "shortplay/")


AI = AISettings()
R2 = R2Settings()

POINT_RULES = {
    "outline": 20,
    "storyboard": 20,
    "video_second": 10,
    "image_asset": 20,
    "audio_asset": 5,
    "compose": 30,
    "voice_clone": 50,
}

DEFAULT_USAGE = {
    "video_total_seconds": 2000,
    "video_used_seconds": 0,
    "image_total": 1000,
    "image_used": 0,
    "export_total": 164,
    "export_used": 0,
}

def apply_usage_defaults(usage: dict) -> dict:
    for key, value in DEFAULT_USAGE.items():
        usage.setdefault(key, value)
    return usage


STATUS_LABEL = {
    "active": "制作中",
    "review": "待审核",
    "draft": "草稿",
    "completed": "已完成",
    "storyboard_ready": "分镜就绪",
    "generating": "生成中",
    "pending": "待生成",
    "needs_review": "待优化",
    "exported": "已导出",
    "failed": "生成失败",
}
