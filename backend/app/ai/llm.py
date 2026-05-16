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


_OPTIMIZE_SYSTEM: dict[str, str] = {
    "project_description": (
        "你是短剧策划专家。将用户输入优化为一段引人入胜的短剧故事简介。"
        "要求：保留核心剧情设定，补充人物动机、冲突悬念和情感张力，"
        "语言简洁有节奏感，适合吸引观众点击观看。"
        "禁止使用画面拍摄描述（如镜头、光影、构图、画面质感等），只写故事内容。"
        "只返回优化后的简介原文，禁止添加任何解释。"
    ),
    "episode_script": (
        "你是短剧编剧。将用户输入优化为生动的剧本文字。"
        "要求：补充场景氛围、人物动作细节和情绪节奏，保留对话核心含义。"
        "只返回优化后的剧本原文，禁止添加任何解释。"
    ),
    "shot_visual": (
        "你是短视频分镜师。将用户输入优化为镜头视觉描述。"
        "要求：补充构图、光线、色调、运镜方式等视觉细节，使描述可直接用于画面生成。"
        "只返回优化后的描述原文，禁止添加任何解释。"
    ),
    "asset_character": (
        "你是 AI 绘图提示词专家。将用户输入优化为角色形象生成提示词。"
        "要求：补充外貌特征、服装细节、光影风格、画面质量描述，适合 AI 图像生成。"
        "只返回优化后的提示词原文，禁止添加任何解释。"
    ),
    "asset_scene": (
        "你是 AI 绘图提示词专家。将用户输入优化为场景环境生成提示词。"
        "要求：补充空间布局、氛围光影、色调材质、画面质量描述，适合 AI 图像生成。"
        "只返回优化后的提示词原文，禁止添加任何解释。"
    ),
    "asset_image": (
        "你是 AI 绘图提示词专家。将用户输入优化为图像生成提示词。"
        "要求：补充视觉细节、风格描述、画面质量参数，适合 AI 图像生成。"
        "只返回优化后的提示词原文，禁止添加任何解释。"
    ),
    "asset_audio": (
        "你是音效设计专家。将用户输入优化为音频生成提示词。"
        "要求：补充音色、节奏、情绪氛围、环境音细节描述。"
        "只返回优化后的提示词原文，禁止添加任何解释。"
    ),
}

_OPTIMIZE_DEFAULT = (
    "你是短剧 AI 创作助手。将用户输入优化为更具体、生动的描述。"
    "只返回优化后的原文，禁止添加任何解释、思考过程、标签或前缀。"
)


def optimize_prompt(prompt: str, context: str) -> str:
    system = _OPTIMIZE_SYSTEM.get(context, _OPTIMIZE_DEFAULT)
    return _chat_text(system, f"原始内容：{prompt}")
