from __future__ import annotations

import os

AUTH_SECRET = os.getenv("SHORTPLAY_AUTH_SECRET", "shortplay-mvp-secret")

POINT_RULES = {
    "outline": 20,
    "storyboard": 20,
    "video_second": 10,
    "image_asset": 20,
    "audio_asset": 5,
    "compose": 30,
}

STATUS_LABEL = {
    "active": "制作中",
    "review": "待审核",
    "draft": "草稿",
    "completed": "已完成",
    "storyboard_ready": "已生成",
    "generating": "生成中",
    "pending": "待生成",
    "needs_review": "待优化",
    "exported": "已导出",
}
