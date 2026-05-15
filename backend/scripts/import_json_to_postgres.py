from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.db import SessionLocal
from app.models import (
    AiJob,
    Asset,
    AssetReference,
    Episode,
    PointLedger,
    Project,
    Shot,
    User,
    VideoTask,
    VideoVersion,
)


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "db.json"


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value), pattern)
        except ValueError:
            pass
    return None


def main() -> None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        for item in data.get("users", []):
            db.merge(User(
                id=item["id"],
                username=item["username"],
                password_hash=item["password_hash"],
                display_name=item.get("display_name") or item["username"],
                role=item.get("role", "user"),
                status=item.get("status", "active"),
                points=int(item.get("points", 0)),
                token=item.get("token"),
                usage_json=item.get("usage", {}),
            ))
        for item in data.get("projects", []):
            db.merge(Project(
                id=item["id"],
                owner_user_id=item.get("owner_user_id", "user_admin"),
                name=item["name"],
                short_name=item.get("short_name") or item["name"][:8],
                description=item.get("description", ""),
                status=item.get("status", "draft"),
                cover=item.get("cover"),
                cover_image_url=item.get("cover_image") or item.get("cover_image_url"),
            ))
        for item in data.get("episodes", []):
            db.merge(Episode(
                id=item["id"],
                project_id=item["project_id"],
                no=int(item["no"]),
                title=item["title"],
                summary=item.get("summary", ""),
                script=item.get("script", ""),
                duration_target=int(item.get("duration_target", 30)),
                status=item.get("status", "draft"),
            ))
        for item in data.get("shots", []):
            db.merge(Shot(
                id=item["id"],
                episode_id=item["episode_id"],
                no=int(item["no"]),
                title=item["title"],
                visual=item.get("visual", ""),
                dialogue=item.get("dialogue", ""),
                characters=item.get("characters", []),
                scene=item.get("scene", ""),
                duration=int(item.get("duration", 3)),
                status=item.get("status", "pending"),
            ))
        for item in data.get("assets", []):
            db.merge(Asset(
                id=item["id"],
                project_id=item["project_id"],
                type=item["type"],
                name=item["name"],
                description=item.get("description", ""),
                initial=item.get("initial") or item["name"][:1],
                image_url=item.get("image") or item.get("image_url"),
                voice_label=item.get("voice"),
                voice_url=item.get("voice_url"),
                speaker_id=item.get("speaker_id"),
                voice_status=item.get("voice_status"),
                provider_meta={},
            ))
            for index, ref in enumerate(item.get("references", []) or []):
                db.merge(AssetReference(
                    id=ref.get("id") or f"{item['id']}_ref_{index + 1}",
                    asset_id=item["id"],
                    type=ref.get("type", "image"),
                    name=ref.get("name", f"参考 {index + 1}"),
                    url=ref.get("url"),
                    note=ref.get("note"),
                    sort_order=index,
                ))
        for item in data.get("video_tasks", []):
            db.merge(VideoTask(
                id=item["id"],
                episode_id=item["episode_id"],
                shot_id=item["shot_id"],
                title=item["title"],
                duration=int(item.get("duration", 1)),
                progress=int(item.get("progress", 0)),
                status=item.get("status", "pending"),
                provider=item.get("provider"),
                provider_task_id=item.get("provider_task_id"),
                preview_url=item.get("preview_url"),
                video_url=item.get("video_url"),
                error=item.get("error"),
            ))
        for item in data.get("video_versions", []):
            db.merge(VideoVersion(
                id=item["id"],
                project_id=item["project_id"],
                episode_id=item["episode_id"],
                name=item["name"],
                description=item.get("description", ""),
                duration=int(item.get("duration", 1)),
                ratio=item.get("ratio", "9:16"),
                status=item.get("status", "review"),
                theme=item.get("theme"),
                preview_url=item.get("preview_url"),
                video_url=item.get("video_url"),
            ))
        for item in data.get("point_ledger", []):
            db.merge(PointLedger(
                id=item["id"],
                user_id=item["user_id"],
                amount=int(item["amount"]),
                type=item.get("type", "consume"),
                scene=item.get("scene", ""),
                description=item.get("description", ""),
                balance_after=int(item.get("balance_after", 0)),
            ))
        for item in data.get("ai_jobs", []):
            db.merge(AiJob(
                id=item["id"],
                user_id=item["user_id"],
                project_id=item.get("project_id"),
                episode_id=item.get("episode_id"),
                shot_id=item.get("shot_id"),
                asset_id=item.get("asset_id"),
                type=item["type"],
                provider=item["provider"],
                provider_task_id=item.get("provider_task_id"),
                status=item.get("status", "running"),
                progress=int(item.get("progress", 0)),
                input_json=item.get("input_json", {}),
                output_json=item.get("output_json", {}),
                error=item.get("error"),
                cost_points=int(item.get("cost_points", 0)),
                completed_at=parse_dt(item.get("completed_at")),
            ))
        db.commit()


if __name__ == "__main__":
    main()
