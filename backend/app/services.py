from __future__ import annotations

from fastapi import HTTPException

from .config import DEFAULT_USAGE, POINT_RULES, STATUS_LABEL
from .schemas import EpisodeDraft, OutlineGenerateRequest
from .security import public_user
from .store import now, uid


def ensure_usage_defaults(usage: dict) -> dict:
    for key, value in DEFAULT_USAGE.items():
        usage.setdefault(key, value)
    return usage


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
    usage = get_user_usage(data, user_id)
    usage["video_used_seconds"] = min(usage["video_total_seconds"], usage["video_used_seconds"] + total_duration)
    return total_duration


def user_response(data: dict, user_id: str) -> dict:
    return public_user(user_in_data(data, user_id))


def optimize_prompt(prompt: str, context: str) -> str:
    """Expand and enrich a user-written prompt for better AI generation results."""
    text = prompt.strip()
    if not text:
        return text

    if context == "asset_character":
        return (
            f"{text}，冷峻面容，短发利落，棱角分明的下颌线，深邃眼神，"
            f"姿态挺拔，双手自然垂落，侧面轮廓光勾勒出肩线与衣褶细节，"
            f"背景为柔和的暗色调虚化，暖色主光从右上方45°打入，"
            f"写实风格，电影级光影，8K画质，超高清晰度"
        )

    if context == "asset_scene":
        return (
            f"{text}，水晶吊灯散发柔和暖光，金色装饰线条勾勒墙面细节，"
            f"大理石地面反射出灯光倒影，前景布置精致花艺装置，"
            f"背景落地窗外映出城市夜景天际线，空间纵深层次分明，"
            f"主色调为暖金与深棕，气氛奢华而内敛，"
            f"超高清渲染，电影级场景美术，16:9宽幅构图"
        )

    if context == "asset_image":
        return (
            f"{text}，画面构图遵循三分法，主体居中偏左，"
            f"前景与背景形成自然景深过渡，色调统一和谐，"
            f"主光源从侧面打入形成明暗对比，细节纹理清晰可见，"
            f"专业美术品质，高清渲染，适合短剧海报与宣传素材"
        )

    if context == "asset_audio":
        return (
            f"{text}，音质清晰无杂音，节奏适中，"
            f"情绪递进自然，前奏轻柔引入，中段饱满有力，尾奏渐弱收束，"
            f"适合30秒短视频循环使用，混音层次分明"
        )

    if context == "project_description":
        parts = [text]
        if "主角" not in text and "她" not in text and "他" not in text:
            parts.insert(0, "以一位年轻女性为主角，")
        if "冲突" not in text and "矛盾" not in text:
            parts.append("核心冲突围绕身份误解与情感背叛展开。")
        if "反转" not in text:
            parts.append("剧情在关键时刻出现身份反转，制造强烈爽感。")
        if "集" not in text:
            parts.append("全剧节奏紧凑，每集30秒，悬念层层递进，适合短剧分集呈现。")
        return "".join(parts)

    if context == "episode_script":
        parts = []
        if "开场" not in text and text[:10]:
            parts.append(f"【开场】{text[:20]}...场景切入，用3秒建立冲突。")
        parts.append(f"\n\n【正文】{text}")
        if "悬念" not in text and "结尾" not in text:
            parts.append("\n\n【结尾悬念】关键信息被揭露但真相未完全浮出，为下一集留下钩子。")
        return "".join(parts)

    if context == "shot_visual":
        return (
            f"{text}，中景镜头，主体居中，"
            f"暖色侧光打出面部与衣物的明暗层次，"
            f"背景虚化处理突出人物，景深过渡自然，"
            f"色调偏暖棕，画面质感强烈，电影级画面，4K超清"
        )

    # general context
    if len(text) < 30:
        return f"{text}，画面精细度高，色调统一，构图讲究，超高清渲染，专业美术品质"
    return text


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
