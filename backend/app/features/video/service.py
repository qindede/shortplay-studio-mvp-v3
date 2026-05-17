from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...ai import video as ai_video
from ...ai.errors import AIError
from ...config import BACKEND_PUBLIC_URL, FFMPEG_PATH, POINT_RULES
from ... import storage
from ..ai_job.service import run_paid_generation as _run_paid_generation
from ..errors import BadRequestError, NotFoundError, ServiceUnavailableError
from ...utils import now
from . import queries


def _video_cost(shot: dict) -> int:
    return max(1, int(shot.get("duration") or 1)) * POINT_RULES["video_second"]


def _reference_image(assets: list[dict], shot: dict) -> str | None:
    character_names = {name.strip() for name in shot.get("characters", []) if name.strip()}
    scene = (shot.get("scene") or "").strip()
    candidates = []
    if character_names:
        candidates.extend(asset for asset in assets if asset.get("type") == "character" and asset.get("name") in character_names)
    if scene:
        candidates.extend(asset for asset in assets if asset.get("type") == "scene" and asset.get("name") == scene)
    candidates.extend(asset for asset in assets if asset.get("type") in {"image", "scene", "character"})
    for asset in candidates:
        media_url = _provider_media_url(asset.get("image"))
        if media_url:
            return media_url
    return None


def _provider_media_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/uploads/") and BACKEND_PUBLIC_URL:
        return f"{BACKEND_PUBLIC_URL.rstrip('/')}{url}"
    return None


def generate_video_for_shot(user: dict, shot_id: str) -> dict:
    from ...features.shot.queries import shot_generation_context
    ctx = shot_generation_context(user, shot_id)
    if not ctx:
        raise NotFoundError("镜头不存在")
    shot, episode, assets = ctx["shot"], ctx.get("episode"), ctx.get("assets", [])
    cost = _video_cost(shot)

    def work(job: dict) -> tuple[dict, dict]:
        provider_task_id = ai_video.create_video_task(
            shot.get("visual") or shot["title"],
            _reference_image(assets, shot),
            shot["duration"],
        )
        task = queries.attach_video_task_to_job(user, shot_id, provider_task_id, job["id"], now())
        return task, {}

    return _run_paid_generation(
        user,
        cost,
        "生成镜头视频",
        f"生成镜头 #{shot['no']}《{shot['title']}》，{max(1, int(shot.get('duration') or 1))}s",
        "video_shot",
        "seedance",
        work,
        complete=False,
        project_id=episode.get("project_id") if episode else None,
        episode_id=shot.get("episode_id"),
        shot_id=shot.get("id"),
    )


def generate_videos_for_episode(user: dict, episode_id: str) -> list[dict]:
    from ...features.storyboard.queries import episode_generation_context
    context = episode_generation_context(user, episode_id)
    if not context:
        raise NotFoundError("剧集不存在")
    shots = context.get("shots", [])
    if not shots:
        raise NotFoundError("分镜不存在")
    tasks = []
    for shot in shots:
        tasks.append(generate_video_for_shot(user, shot["id"]))
    return tasks


def compose_episode(user: dict, episode_id: str, payload: Any, compose_video_file: Callable[[list[dict]], str]) -> dict:
    context = queries.compose_context(user, episode_id)
    if not context:
        raise NotFoundError("剧集不存在")
    shots = context.get("shots", [])
    if not shots or any(shot.get("status") != "completed" for shot in shots):
        raise BadRequestError("所有镜头完成后才能合成本集视频")

    def work(job: dict) -> tuple[dict, dict | None]:
        shot_order = {shot["id"]: shot["no"] for shot in shots}
        video_url = compose_video_file(sorted(context.get("video_tasks", []), key=lambda item: shot_order.get(item.get("shot_id"), 0)))
        version = queries.save_composed_version(user, episode_id, payload, video_url, 0, now(), charge=False, job_id=job["id"])
        return version, None

    return _run_paid_generation(
        user,
        POINT_RULES["compose"],
        "合成成片",
        f"合成《{context['episode']['title']}》成片版本",
        "compose",
        "ffmpeg",
        work,
        complete=False,
        failure_message="合成失败",
        project_id=context["project"]["id"],
        episode_id=episode_id,
    )


def compose_video_file(tasks: list[dict]) -> str:
    """Standalone function that uses ffmpeg to compose shot videos into a single episode video."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        inputs = []
        for index, task in enumerate(tasks, start=1):
            url = task.get("video_url") or task.get("preview_url")
            if not url or not url.startswith("/uploads/"):
                raise BadRequestError("镜头视频文件不完整，无法合成")
            data, _ = storage.get_object(url.removeprefix("/uploads/"))
            path = tmpdir / f"{index:03d}.mp4"
            path.write_bytes(data)
            inputs.append(path)
        concat = tmpdir / "inputs.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in inputs), encoding="utf-8")
        output = tmpdir / "episode.mp4"
        try:
            subprocess.run(
                [FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(output)],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as exc:
            raise ServiceUnavailableError("服务器未配置 ffmpeg") from exc
        except subprocess.CalledProcessError as exc:
            raise ServiceUnavailableError("视频合成失败") from exc
        key = storage.make_object_key("composed", "episode.mp4", ".mp4")
        return storage.put_bytes(output.read_bytes(), key, "video/mp4")


def list_video_tasks_with_poll(user: dict, episode_id: str) -> list[dict]:
    """Poll video task status from provider and return updated tasks."""
    from ...features.workspace.queries import episode_workspace
    payload = episode_workspace(user, episode_id)
    if payload is None:
        raise NotFoundError("剧集不存在")
    tasks = payload["video_tasks"]
    for task in tasks:
        if task.get("status") != "generating" or not task.get("provider_task_id"):
            continue
        from ...ai.video import query_video_task
        try:
            remote = query_video_task(task["provider_task_id"])
        except AIError:
            continue
        queries.update_video_task_from_provider(task, remote)
    return sorted(tasks, key=lambda t: t.get("updated_at", ""), reverse=True)
