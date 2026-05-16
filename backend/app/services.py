from __future__ import annotations

from fastapi import HTTPException

from .config import POINT_RULES, STATUS_LABEL, apply_usage_defaults
from .store import now, uid


def ensure_usage_defaults(usage: dict) -> dict:
    return apply_usage_defaults(usage)


def not_found(name: str):
    raise HTTPException(status_code=404, detail=f"{name} not found")


def find_by_id(rows: list[dict], row_id: str, name: str) -> dict:
    row = next((item for item in rows if item.get("id") == row_id), None)
    if not row:
        not_found(name)
    return row


def user_in_data(data: dict, user_id: str) -> dict:
    return find_by_id(data.get("users", []), user_id, "user")


def change_points(data: dict, user_id: str, amount: int, kind: str, scene: str, description: str) -> dict:
    user = user_in_data(data, user_id)
    current_points = int(user.get("points", 0))
    if current_points + amount < 0:
        raise HTTPException(status_code=402, detail=f"积分不足：当前 {current_points}，本次需要 {-amount}")

    user["points"] = current_points + amount
    entry = {
        "id": uid("ledger"),
        "user_id": user_id,
        "username": user.get("username"),
        "display_name": user.get("display_name") or user.get("username"),
        "amount": amount,
        "type": kind,
        "scene": scene,
        "description": description,
        "balance_after": user["points"],
        "created_at": now(),
    }
    data.setdefault("point_ledger", []).insert(0, entry)
    return entry


def get_user_projects(data: dict, user_id: str) -> list[dict]:
    return [p for p in data["projects"] if p.get("owner_user_id") == user_id]


def verify_project_ownership(data: dict, project_id: str, user_id: str) -> dict:
    project = next((p for p in data["projects"] if p["id"] == project_id), None)
    if not project:
        not_found("project")
    if project.get("owner_user_id") != user_id:
        raise HTTPException(status_code=403, detail="无权访问此项目")
    return project


def get_user_usage(data: dict, user_id: str) -> dict:
    user = user_in_data(data, user_id)
    user.setdefault("usage", {})
    return ensure_usage_defaults(user["usage"])


def enrich_project(data: dict, project: dict) -> dict:
    project_id = project["id"]
    episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
    assets = [a for a in data["assets"] if a["project_id"] == project_id]
    versions = [v for v in data["video_versions"] if v["project_id"] == project_id]
    return {
        **project,
        "status_label": STATUS_LABEL.get(project.get("status"), project.get("status")),
        "episode_count": len(episodes),
        "asset_count": len(assets),
        "version_count": len(versions),
    }


def enrich_episode(data: dict, episode: dict) -> dict:
    episode_id = episode["id"]
    shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
    versions = [v for v in data["video_versions"] if v["episode_id"] == episode_id]
    return {
        **episode,
        "status_label": STATUS_LABEL.get(episode.get("status"), episode.get("status")),
        "shot_count": len(shots),
        "version_count": len(versions),
    }


def usage_with_members(data: dict, user_id: str | None = None) -> dict:
    if user_id:
        usage = {**get_user_usage(data, user_id)}
    else:
        usage = {**data.get("usage", {})}
    usage["team_members"] = len([u for u in data.get("users", []) if u.get("status") == "active"])
    return usage


def touch_project(data: dict, project_id: str, timestamp: str | None = None) -> None:
    project = next((p for p in data["projects"] if p["id"] == project_id), None)
    if project:
        project["updated_at"] = timestamp or now()


def touch_episode_and_project(data: dict, episode: dict, timestamp: str | None = None) -> None:
    ts = timestamp or now()
    episode["updated_at"] = ts
    touch_project(data, episode["project_id"], ts)


def renumber(rows: list[dict]) -> None:
    rows.sort(key=lambda item: item["no"])
    for index, item in enumerate(rows, start=1):
        item["no"] = index


def add_ai_job(
    data: dict,
    user_id: str,
    job_type: str,
    provider: str,
    cost: int,
    status: str = "succeeded",
    progress: int = 100,
    provider_task_id: str | None = None,
    error: str | None = None,
    **links,
) -> dict:
    ts = now()
    job = {
        "id": uid("job"),
        "user_id": user_id,
        "type": job_type,
        "provider": provider,
        "provider_task_id": provider_task_id,
        "status": status,
        "progress": progress,
        "cost_points": cost,
        "input_json": {},
        "output_json": {},
        "error": error,
        "created_at": ts,
        "updated_at": ts,
        "completed_at": ts if status in {"succeeded", "failed", "cancelled"} else "",
        **{key: value for key, value in links.items() if value},
    }
    data.setdefault("ai_jobs", []).insert(0, job)
    return job


def refund_once(data: dict, user_id: str, task: dict, amount: int, scene: str, description: str) -> None:
    output_json = task.get("output_json") if isinstance(task.get("output_json"), dict) else {}
    if task.get("refunded") or output_json.get("refunded") or amount <= 0:
        return
    change_points(data, user_id, amount, "refund", scene, description)
    task["refunded"] = True
    if "output_json" in task:
        output_json["refunded"] = True
        task["output_json"] = output_json


def comparable_asset_names(asset: dict) -> set[str]:
    name = (asset.get("name") or "").strip()
    names = {name}
    if "：" in name:
        names.add(name.rsplit("：", 1)[-1].strip())
    if ":" in name:
        names.add(name.rsplit(":", 1)[-1].strip())
    return {item for item in names if item}


def normalize_refs(refs: list[dict] | None) -> list[dict]:
    normalized = []
    for index, ref in enumerate(refs or [], start=1):
        normalized.append({
            "id": ref.get("id") or uid("ref"),
            "type": ref.get("type", "image"),
            "name": ref.get("name") or f"参考 {index:02d}",
            "url": ref.get("url"),
            "note": ref.get("note"),
        })
    return normalized
