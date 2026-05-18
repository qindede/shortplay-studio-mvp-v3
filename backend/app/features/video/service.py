from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ...ai import video as ai_video
from ...ai.errors import AIError
from ...config import BACKEND_PUBLIC_URL, FFMPEG_PATH, POINT_RULES
from ...db import SessionLocal
from ...models import AiJob, Episode, Project, Shot
from ...serializers import _video_job_dict
from ... import storage
from ..ai_job.service import run_paid_generation as _run_paid_generation
from ..errors import BadRequestError, NotFoundError, ServiceUnavailableError
from ...utils import now
from . import db


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
    from ...features.shot.service import get_generation_context as shot_generation_context
    ctx = shot_generation_context(user, shot_id)
    shot, episode, assets = ctx["shot"], ctx.get("episode"), ctx.get("assets", [])
    cost = _video_cost(shot)

    def work(job: dict) -> tuple[dict, dict]:
        provider_task_id = ai_video.create_video_task(
            shot.get("visual") or shot["title"],
            _reference_image(assets, shot),
            shot["duration"],
        )
        # _run_paid_generation 已创建 AiJob 并扣费，这里只更新 provider_task_id 和 shot 状态
        result = db.update_job_for_video_shot(job["id"], shot_id, provider_task_id, now())
        if not result:
            raise NotFoundError("镜头不存在")
        return result, {}

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
    from ...features.storyboard.service import get_episode_generation_context as episode_generation_context
    context = episode_generation_context(user, episode_id)
    shots = context.get("shots", [])
    if not shots:
        raise NotFoundError("分镜不存在")
    tasks = []
    for shot in shots:
        tasks.append(generate_video_for_shot(user, shot["id"]))
    return tasks


def compose_episode(user: dict, episode_id: str, payload: Any, compose_video_file: Callable[[list[dict]], str]) -> dict:
    context = db.compose_context(user, episode_id)
    if not context:
        raise NotFoundError("剧集不存在")
    shots = context.get("shots", [])
    if not shots or any(shot.get("status") != "completed" for shot in shots):
        raise BadRequestError("所有镜头完成后才能合成本集视频")
    video_jobs = context.get("video_jobs", [])
    shots_with_video = {j.get("shot_id") for j in video_jobs}
    if any(shot["id"] not in shots_with_video for shot in shots):
        raise BadRequestError("所有镜头视频生成成功后才能合成")

    def work(job: dict) -> tuple[dict, dict | None]:
        shot_order = {shot["id"]: shot["no"] for shot in shots}
        video_url = compose_video_file(sorted(context.get("video_jobs", []), key=lambda item: shot_order.get(item.get("shot_id"), 0)))
        version = db.save_composed_version(user, episode_id, payload, video_url, 0, now(), charge=False, job_id=job["id"])
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


def list_video_jobs_with_poll(user: dict, episode_id: str) -> list[dict]:
    """Poll video job status from provider and return updated jobs."""
    with SessionLocal() as session:
        # Verify user owns this episode
        episode = session.scalar(
            select(Episode)
            .join(Project, Project.id == Episode.project_id)
            .where(Episode.id == episode_id, Project.owner_user_id == user["id"])
        )
        if not episode:
            raise NotFoundError("剧集不存在")

        jobs = list(session.scalars(
            select(AiJob)
            .where(AiJob.episode_id == episode_id, AiJob.type == "video_shot")
            .order_by(AiJob.updated_at.desc())
        ))
        shot_ids = {j.shot_id for j in jobs if j.shot_id}
        shots = {s.id: s for s in session.scalars(select(Shot).where(Shot.id.in_(shot_ids)))} if shot_ids else {}

    result = []
    for job in jobs:
        if job.status == "running" and job.provider_task_id:
            from ...ai.video import query_video_task
            try:
                remote = query_video_task(job.provider_task_id)
                db.update_video_job_from_provider(job.id, remote)
                # Re-fetch updated job
                with SessionLocal() as session:
                    job = session.get(AiJob, job.id)
                    if not job:
                        continue
            except AIError:
                pass
        shot = shots.get(job.shot_id)
        result.append(_video_job_dict(job, shot))

    return sorted(result, key=lambda t: t.get("updated_at", ""), reverse=True)
