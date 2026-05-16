from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from ..config import AI
from ..schemas import EpisodeDraft, OutlineGenerateRequest
from .client import post_json, require_key
from .errors import AIOutputSchemaError
from .schemas import OutlineResult, StoryboardResult


def _chat_json(system: str, user: str) -> Any:
    key = require_key(AI.minimax_api_key, "MINIMAX_API_KEY")
    payload = {
        "model": AI.minimax_text_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    body = post_json(
        f"{AI.minimax_base_url.rstrip('/')}/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        payload,
        AI.request_timeout,
    )
    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIOutputSchemaError("LLM did not return valid JSON") from exc


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_tags(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def _chat_text(system: str, user: str) -> str:
    key = require_key(AI.minimax_api_key, "MINIMAX_API_KEY")
    payload = {
        "model": AI.minimax_text_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    body = post_json(
        f"{AI.minimax_base_url.rstrip('/')}/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        payload,
        AI.request_timeout,
    )
    content = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return _strip_think_tags(content)


def generate_outline(payload: OutlineGenerateRequest) -> list[EpisodeDraft]:
    data = _chat_json(
        "你是短剧编剧。只返回 JSON，格式为 {\"episodes\": [...] }。",
        (
            f"为短剧《{payload.name}》生成 {payload.episode_count} 集大纲。"
            f"设定：{payload.description}。每集包含 title、summary、script、duration_target。"
        ),
    )
    try:
        result = OutlineResult.model_validate(data)
    except ValidationError as exc:
        raise AIOutputSchemaError("Outline JSON schema validation failed") from exc
    return [EpisodeDraft(**episode.model_dump()) for episode in result.episodes]


def generate_storyboard(project: dict, episode: dict, assets: list[dict]) -> list[dict]:
    asset_text = "\n".join(f"- {a.get('type')}: {a.get('name')} {a.get('description', '')}" for a in assets[:20])
    data = _chat_json(
        "你是短剧分镜师。只返回 JSON，格式为 {\"shots\": [...] }。",
        (
            f"项目：{project.get('name')}\n"
            f"剧集：{episode.get('title')}\n"
            f"剧情摘要：{episode.get('summary')}\n"
            f"剧本：{episode.get('script')}\n"
            f"可用素材：\n{asset_text}\n"
            "生成竖屏短剧分镜。每个镜头包含 title、visual、dialogue、characters、scene、duration。"
        ),
    )
    try:
        result = StoryboardResult.model_validate(data)
    except ValidationError as exc:
        raise AIOutputSchemaError("Storyboard JSON schema validation failed") from exc
    return [shot.model_dump() for shot in result.shots]


def optimize_prompt(prompt: str, context: str) -> str:
    return _chat_text(
        "你是短剧 AI 生成提示词优化助手。只返回优化后的中文提示词原文，禁止添加任何解释、思考过程、标签或前缀。",
        f"场景：{context}\n原始提示词：{prompt}",
    )
