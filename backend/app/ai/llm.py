from __future__ import annotations

import json
import re
import math
from typing import Any

from pydantic import ValidationError

from ..config import AI
from ..schemas import EpisodeDraft, OutlineGenerateRequest
from .client import post_json, require_key
from .errors import AIOutputSchemaError
from .schemas import OutlineResult, StoryboardResult


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)
_INT_RE = re.compile(r"\d+")


_STORYBOARD_LIST_KEYS = ("shots", "storyboard", "分镜", "镜头", "镜头列表", "shot_list")
_STORYBOARD_FIELD_KEYS = {
    "title": ("title", "标题", "镜头标题", "名称", "name"),
    "visual": ("visual", "画面", "画面描述", "视觉描述", "镜头描述", "description"),
    "dialogue": ("dialogue", "台词", "对白", "旁白", "line", "lines"),
    "characters": ("characters", "角色", "人物", "出场人物", "character"),
    "scene": ("scene", "场景", "地点", "场景地点", "location"),
    "duration": ("duration", "时长", "镜头时长", "秒数", "duration_seconds"),
}


def _strip_think_tags(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def _extract_json(text: str) -> str:
    """Strip think tags and markdown fences, then locate the first JSON object/array."""
    text = _strip_think_tags(text)
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    start = None
    end = None
    for i, ch in enumerate(text):
        if ch in "{[" and start is None:
            start = i
        if ch in "}]":
            end = i
    if start is not None and end is not None:
        return text[start : end + 1]
    return text


def _chat_json(system: str, user: str, timeout: float | None = None) -> Any:
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
        timeout or AI.request_timeout,
    )
    raw = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    content = _extract_json(raw)
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIOutputSchemaError("LLM did not return valid JSON") from exc


def _first_value(data: dict, keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(_coerce_text(item) for item in value if item is not None).strip()
    return str(value).strip()


def _coerce_characters(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_coerce_text(item) for item in value if _coerce_text(item)]
    text = _coerce_text(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[,，、/]\s*", text) if item.strip()]


def _coerce_duration(value: Any) -> int:
    if isinstance(value, int):
        duration = value
    elif isinstance(value, float):
        duration = round(value)
    else:
        match = _INT_RE.search(_coerce_text(value))
        duration = int(match.group()) if match else 3
    return max(1, min(60, duration))


def _normalize_storyboard_data(data: Any) -> dict:
    if isinstance(data, list):
        shots = data
    elif isinstance(data, dict):
        shots = None
        for key in _STORYBOARD_LIST_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                shots = value
                break
        if shots is None:
            shots = [data]
    else:
        return {"shots": []}

    normalized = []
    for index, item in enumerate(shots, start=1):
        if not isinstance(item, dict):
            continue
        title = _coerce_text(_first_value(item, _STORYBOARD_FIELD_KEYS["title"]))
        visual = _coerce_text(_first_value(item, _STORYBOARD_FIELD_KEYS["visual"]))
        dialogue = _coerce_text(_first_value(item, _STORYBOARD_FIELD_KEYS["dialogue"]))
        scene = _coerce_text(_first_value(item, _STORYBOARD_FIELD_KEYS["scene"]))
        normalized.append(
            {
                "title": title or f"镜头 {index}",
                "visual": visual,
                "dialogue": dialogue,
                "characters": _coerce_characters(_first_value(item, _STORYBOARD_FIELD_KEYS["characters"], [])),
                "scene": scene,
                "duration": _coerce_duration(_first_value(item, _STORYBOARD_FIELD_KEYS["duration"], 3)),
            }
        )
    return {"shots": normalized}


def _storyboard_shot_count(episode: dict) -> int:
    duration = episode.get("duration_target") or episode.get("duration") or 30
    try:
        seconds = int(duration)
    except (TypeError, ValueError):
        seconds = 30
    return max(4, min(12, math.ceil(seconds / 5)))


def _chat_text(system: str, user: str, timeout: float | None = None) -> str:
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
        timeout or AI.request_timeout,
    )
    content = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return _strip_think_tags(content)


def generate_outline(payload: OutlineGenerateRequest) -> list[EpisodeDraft]:
    data = _chat_json(
        (
            "你是短剧编剧。只返回 JSON，不要输出任何其他文字。\n"
            "严格按以下格式返回：\n"
            '{"episodes": [\n'
            '  {"title": "集标题", "summary": "剧情摘要", "script": "剧本正文", "duration_target": 30}\n'
            "]}\n"
            "字段说明：title(字符串,必填), summary(字符串), script(字符串), duration_target(整数,秒)。"
        ),
        (
            f"为短剧《{payload.name}》生成 {payload.episode_count} 集大纲。"
            f"设定：{payload.description}。"
        ),
        timeout=AI.generation_timeout,
    )
    try:
        result = OutlineResult.model_validate(data)
    except ValidationError as exc:
        raise AIOutputSchemaError("Outline JSON schema validation failed") from exc
    return [EpisodeDraft(**episode.model_dump()) for episode in result.episodes]


def generate_storyboard(project: dict, episode: dict, assets: list[dict]) -> list[dict]:
    asset_text = "\n".join(f"- {a.get('type')}: {a.get('name')} {a.get('description', '')}" for a in assets[:20])
    shot_count = _storyboard_shot_count(episode)
    data = _chat_json(
        (
            "你是短剧分镜师。只返回 JSON，不要输出任何其他文字。\n"
            "严格按以下格式返回：\n"
            '{"shots": [\n'
            '  {"title": "镜头标题", "visual": "画面描述", "dialogue": "台词", "characters": ["角色名"], "scene": "场景", "duration": 3}\n'
            "]}\n"
            "必须使用英文键名 shots/title/visual/dialogue/characters/scene/duration。"
            "不要使用中文键名，不要返回 markdown，不要把 JSON 放进字符串。"
            "字段说明：title(字符串,必填), visual(字符串), dialogue(字符串), characters(字符串数组), scene(字符串), duration(整数,秒)。"
        ),
        (
            f"项目：{project.get('name')}\n"
            f"剧集：{episode.get('title')}\n"
            f"剧情摘要：{episode.get('summary')}\n"
            f"剧本：{episode.get('script')}\n"
            f"可用素材：\n{asset_text or '暂无，可根据剧情自行提取角色和场景。'}\n"
            f"生成 {shot_count} 个竖屏短剧分镜镜头。每个镜头 2-8 秒，按剧情顺序推进。"
        ),
        timeout=AI.generation_timeout,
    )
    try:
        data = _normalize_storyboard_data(data)
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

_OPTIMIZE_NAME_SUFFIX = (
    "以下是短剧《{name}》的相关内容，优化时必须紧扣该剧的名称、题材和风格，"
    "确保输出内容与剧名高度相关，不要偏离该剧的故事方向。"
)


def optimize_prompt(prompt: str, context: str, project_name: str = "") -> str:
    system = _OPTIMIZE_SYSTEM.get(context, _OPTIMIZE_DEFAULT)
    if project_name:
        system += _OPTIMIZE_NAME_SUFFIX.format(name=project_name)
    return _chat_text(system, f"原始内容：{prompt}")
