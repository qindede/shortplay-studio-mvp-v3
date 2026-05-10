from __future__ import annotations

from fastapi import HTTPException

from .config import POINT_RULES, STATUS_LABEL
from .schemas import EpisodeDraft, OutlineGenerateRequest
from .security import public_user
from .store import now, uid


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


def usage_with_members(data: dict) -> dict:
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


def build_project_outline(payload: OutlineGenerateRequest) -> list[EpisodeDraft]:
    name = payload.name.strip()
    description = payload.description.strip()
    beats = [
        ("强钩子开场", "用最强冲突打开故事，主角被推进无法回头的局面。"),
        ("误会升级", "核心人物互相试探，隐藏身份或关键秘密被第一次触碰。"),
        ("反派施压", "对手主动出击，主角的目标、尊严或关系受到明显威胁。"),
        ("关键反转", "主角拿到新线索，局势从被动挨打转向主动布局。"),
        ("情感裂痕", "最重要的关系出现误解，短剧的情绪张力被推高。"),
        ("证据浮出", "真相碎片被串联起来，观众看到下一轮爆点的入口。"),
        ("当众反击", "主角在公开场合完成一次强反击，爽点集中释放。"),
        ("身份揭露", "核心身份或幕后关系被揭开，人物站位发生变化。"),
        ("终局逼近", "反派孤注一掷，主角必须在有限时间内做出选择。"),
        ("高潮收束", "主角完成最终反转，并给下一季或番外留下余味。"),
    ]

    episodes: list[EpisodeDraft] = []
    for index in range(payload.episode_count):
        beat_title, beat_summary = beats[index % len(beats)]
        summary = f"{description} 本集聚焦“{beat_title}”：{beat_summary}"
        script = (
            f"项目《{name}》第{index + 1}集。"
            f"剧情摘要：{summary} "
            "建议用开场三秒冲突、人物对峙、结尾悬念组织脚本。"
        )
        episodes.append(EpisodeDraft(title=beat_title, summary=summary, script=script, duration_target=30))
    return episodes


def build_storyboard(episode: dict) -> list[dict]:
    scene = "核心剧情场景"
    base = [
        ("冲突进入", "主角突然进入关键场景，所有人的视线集中到她身上。", "这件事，不能就这样结束。", ["主角"], 3),
        ("当众质疑", "反派和围观者形成压力，现场气氛迅速变紧张。", "她是谁？凭什么出现在这里？", ["反派"], 4),
        ("关键人物起身", "关键人物从人群中起身，镜头缓慢推进，现场安静下来。", "", ["关键人物"], 5),
        ("身份反转", "关键人物站到主角身边，公开给出决定性信息，众人震惊。", "她才是我真正要保护的人。", ["主角", "关键人物"], 6),
    ]
    return [
        {
            "id": uid("shot"),
            "episode_id": episode["id"],
            "no": i,
            "title": title,
            "visual": visual,
            "dialogue": dialogue,
            "characters": characters,
            "scene": scene,
            "duration": duration,
            "status": "pending",
            "updated_at": now(),
        }
        for i, (title, visual, dialogue, characters, duration) in enumerate(base, start=1)
    ]


def create_or_complete_video_task(data: dict, shot: dict) -> dict:
    task = next((t for t in data["video_tasks"] if t["shot_id"] == shot["id"]), None)
    if not task:
        task = {
            "id": uid("task"),
            "episode_id": shot["episode_id"],
            "shot_id": shot["id"],
            "title": shot["title"],
            "duration": shot["duration"],
            "progress": 100,
            "status": "completed",
            "updated_at": now(),
        }
        data["video_tasks"].append(task)
    else:
        task.update(
            {
                "title": shot["title"],
                "duration": shot["duration"],
                "progress": 100,
                "status": "completed",
                "updated_at": now(),
            }
        )

    shot["status"] = "completed"
    shot["updated_at"] = now()
    return task


def consume_for_video(data: dict, user_id: str, shots: list[dict], scene: str, description: str) -> int:
    total_duration = sum(max(1, int(s["duration"])) for s in shots)
    change_points(data, user_id, -(total_duration * POINT_RULES["video_second"]), "consume", scene, description)
    usage = data["usage"]
    usage["video_used_seconds"] = min(usage["video_total_seconds"], usage["video_used_seconds"] + total_duration)
    return total_duration


def user_response(data: dict, user_id: str) -> dict:
    return public_user(user_in_data(data, user_id))
