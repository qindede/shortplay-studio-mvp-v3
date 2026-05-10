from __future__ import annotations

import hashlib
import json
import os
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

DATA_PATH = Path(os.getenv("SHORTPLAY_DB", Path(__file__).resolve().parent.parent / "data" / "db.json"))
_LOCK = threading.Lock()
AUTH_SECRET = os.getenv("SHORTPLAY_AUTH_SECRET", "shortplay-mvp-secret")


def default_password_hash(password: str) -> str:
    return hashlib.sha256(f"{AUTH_SECRET}:{password}".encode("utf-8")).hexdigest()


def default_users() -> list[dict[str, Any]]:
    ts = now()
    default_usage = {
        "video_total_seconds": 2000,
        "video_used_seconds": 0,
        "image_total": 1000,
        "image_used": 0,
        "export_total": 164,
        "export_used": 0,
    }
    return [
        {
            "id": "user_admin",
            "username": "admin",
            "display_name": "管理员",
            "password_hash": default_password_hash("admin123"),
            "role": "admin",
            "status": "active",
            "points": 100000,
            "token": "",
            "usage": {**default_usage},
            "created_at": ts,
            "last_login": "",
        },
        {
            "id": "user_demo",
            "username": "demo",
            "display_name": "演示用户",
            "password_hash": default_password_hash("demo123"),
            "role": "user",
            "status": "active",
            "points": 2000,
            "token": "",
            "usage": {**default_usage},
            "created_at": ts,
            "last_login": "",
        },
    ]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def seed_data() -> dict[str, Any]:
    project_id = "proj_haomen"
    episodes = [
        {
            "id": "ep_001",
            "project_id": project_id,
            "no": 1,
            "title": "订婚现场的陌生女人",
            "summary": "女主闯入订婚现场，众人误以为她是服务员。",
            "script": "女主误闯豪门订婚现场，被众人嘲笑是服务员。反派未婚妻当众羞辱她，男主原本沉默，最后当众牵起女主的手，宣布她才是真正的未婚妻。",
            "duration_target": 30,
            "status": "storyboard_ready",
            "updated_at": now(),
        },
        {
            "id": "ep_002",
            "project_id": project_id,
            "no": 2,
            "title": "她才是真正的继承人",
            "summary": "男主当众牵起女主的手，揭开她的真实身份。",
            "script": "男主牵起女主的手，告诉所有宾客她才是真正的继承人。反派未婚妻质疑她的身份，管家拿出尘封多年的亲子鉴定。",
            "duration_target": 25,
            "status": "generating",
            "updated_at": now(),
        },
        {
            "id": "ep_003",
            "project_id": project_id,
            "no": 3,
            "title": "旧照片里的秘密",
            "summary": "女主在旧相册中发现自己与豪门家族的关系。",
            "script": "女主回到老宅，在母亲遗物里发现一张旧照片。照片背后写着一个豪门家族的姓氏，她开始怀疑自己的真实身世。",
            "duration_target": 30,
            "status": "draft",
            "updated_at": now(),
        },
        {
            "id": "ep_004",
            "project_id": project_id,
            "no": 4,
            "title": "未婚妻的反击",
            "summary": "反派不甘失败，公开质疑女主身份。",
            "script": "苏晴不甘失败，公开质疑林晚的身份，试图用一份伪造的资料扭转局面。顾沉提前安排的人出现，揭穿她的谎言。",
            "duration_target": 20,
            "status": "needs_review",
            "updated_at": now(),
        },
    ]
    shots = [
        {
            "id": "shot_001",
            "episode_id": "ep_001",
            "no": 1,
            "title": "女主推门进入",
            "visual": "豪华宴会厅大门被推开，女主站在门口，灯光照在她脸上。",
            "dialogue": "这场订婚，不能继续。",
            "characters": ["林晚"],
            "scene": "豪门宴会厅",
            "duration": 3,
            "status": "completed",
            "updated_at": now(),
        },
        {
            "id": "shot_002",
            "episode_id": "ep_001",
            "no": 2,
            "title": "宾客议论",
            "visual": "宾客回头，反派未婚妻冷笑，现场气氛变得尖锐。",
            "dialogue": "她是谁？也配来这里？",
            "characters": ["苏晴"],
            "scene": "豪门宴会厅",
            "duration": 4,
            "status": "generating",
            "updated_at": now(),
        },
        {
            "id": "shot_003",
            "episode_id": "ep_001",
            "no": 3,
            "title": "男主起身",
            "visual": "男主从主桌缓慢起身，镜头推进，所有人安静下来。",
            "dialogue": "",
            "characters": ["顾沉"],
            "scene": "豪门宴会厅",
            "duration": 5,
            "status": "pending",
            "updated_at": now(),
        },
        {
            "id": "shot_004",
            "episode_id": "ep_001",
            "no": 4,
            "title": "身份反转",
            "visual": "男主走到女主身边，牵起她的手，众人震惊。",
            "dialogue": "她才是我的未婚妻。",
            "characters": ["林晚", "顾沉"],
            "scene": "豪门宴会厅",
            "duration": 6,
            "status": "pending",
            "updated_at": now(),
        },
    ]
    return {
        "projects": [
            {
                "id": project_id,
                "name": "豪门错爱：身份反转短剧",
                "short_name": "豪门错爱",
                "description": "女主误闯订婚现场，男主当众宣布她才是真正的未婚妻。",
                "status": "active",
                "owner": "演示用户",
                "owner_user_id": "user_demo",
                "cover": "dark",
                "updated_at": now(),
            },
            {
                "id": "proj_qianjin",
                "name": "真假千金：身世揭露系列",
                "short_name": "真假千金",
                "description": "医院门口身份揭露，亲生母亲当场崩溃。",
                "status": "review",
                "owner": "演示用户",
                "owner_user_id": "user_demo",
                "cover": "blue",
                "updated_at": now(),
            },
            {
                "id": "proj_zhuixu",
                "name": "赘婿逆袭：打脸剧情系列",
                "short_name": "赘婿逆袭",
                "description": "男主被羞辱后亮出集团继承人身份。",
                "status": "draft",
                "owner": "管理员",
                "owner_user_id": "user_admin",
                "cover": "green",
                "updated_at": now(),
            },
            {
                "id": "proj_rebirth",
                "name": "重生复仇：职场逆袭",
                "short_name": "重生复仇",
                "description": "女主重生回到入职第一天，提前识破同事陷害。",
                "status": "active",
                "owner": "管理员",
                "owner_user_id": "user_admin",
                "cover": "purple",
                "updated_at": now(),
            },
        ],
        "episodes": episodes,
        "shots": shots,
        "assets": [
            {
                "id": "asset_linwan",
                "project_id": project_id,
                "type": "character",
                "name": "女主：林晚",
                "description": "24岁，清冷倔强，白色礼裙，适合逆袭、误会、身份反转剧情。",
                "ref_count": 8,
                "initial": "林",
                "updated_at": now(),
            },
            {
                "id": "asset_guchen",
                "project_id": project_id,
                "type": "character",
                "name": "男主：顾沉",
                "description": "30岁，豪门继承人，黑色西装，冷峻克制，适合霸总剧情。",
                "ref_count": 6,
                "initial": "顾",
                "updated_at": now(),
            },
            {
                "id": "asset_suqing",
                "project_id": project_id,
                "type": "character",
                "name": "反派：苏晴",
                "description": "26岁，精致强势，礼服造型，适合冲突和反击剧情。",
                "ref_count": 5,
                "initial": "苏",
                "updated_at": now(),
            },
            {
                "id": "asset_banquet",
                "project_id": project_id,
                "type": "scene",
                "name": "豪门宴会厅",
                "description": "金色灯光、大理石地面、订婚仪式布置，适合身份揭露剧情。",
                "ref_count": 4,
                "initial": "宴",
                "updated_at": now(),
            },
            {
                "id": "asset_hospital",
                "project_id": project_id,
                "type": "scene",
                "name": "医院走廊",
                "description": "冷色调、白色灯光、紧张氛围，适合身世揭露和亲情冲突。",
                "ref_count": 3,
                "initial": "医",
                "updated_at": now(),
            },
        ],
        "video_tasks": [
            {
                "id": "task_001",
                "episode_id": "ep_001",
                "shot_id": "shot_001",
                "title": "女主推门进入",
                "duration": 3,
                "progress": 100,
                "status": "completed",
                "updated_at": now(),
            },
            {
                "id": "task_002",
                "episode_id": "ep_001",
                "shot_id": "shot_002",
                "title": "宾客议论",
                "duration": 4,
                "progress": 66,
                "status": "generating",
                "updated_at": now(),
            },
        ],
        "video_versions": [
            {
                "id": "ver_001",
                "project_id": project_id,
                "episode_id": "ep_001",
                "name": "第01集 版本A",
                "description": "强冲突开头 / 30s / 已导出",
                "duration": 30,
                "ratio": "9:16",
                "status": "exported",
                "theme": "dark",
                "created_at": now(),
            },
            {
                "id": "ver_002",
                "project_id": project_id,
                "episode_id": "ep_001",
                "name": "第01集 版本B",
                "description": "身份揭露开头 / 15s / 待审核",
                "duration": 15,
                "ratio": "9:16",
                "status": "review",
                "theme": "blue",
                "created_at": now(),
            },
        ],
        "usage": {
            "video_total_seconds": 2000,
            "video_used_seconds": 1286,
            "image_total": 1000,
            "image_used": 438,
            "export_total": 164,
            "export_used": 126,
            "team_members": 2,
        },
        "users": default_users(),
        "point_ledger": [
            {
                "id": "ledger_admin_init",
                "user_id": "user_admin",
                "username": "admin",
                "display_name": "管理员",
                "amount": 100000,
                "type": "init",
                "scene": "系统初始化",
                "description": "管理员初始积分",
                "balance_after": 100000,
                "created_at": now(),
            },
            {
                "id": "ledger_demo_init",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": 2000,
                "type": "init",
                "scene": "系统初始化",
                "description": "演示用户初始积分",
                "balance_after": 2000,
                "created_at": now(),
            },
        ],
    }


def normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    changed = False
    # Migrate projects without owner_user_id - assign to admin
    for project in data.get("projects", []):
        if "owner_user_id" not in project:
            project["owner_user_id"] = "user_admin"
            changed = True
    if "users" not in data:
        data["users"] = default_users()
        changed = True
    else:
        for user in data["users"]:
            user.setdefault("display_name", user.get("username", "用户"))
            user.setdefault("role", "user")
            user.setdefault("status", "active")
            user.setdefault("points", 1000)
            user.setdefault("token", "")
            user.setdefault("created_at", now())
            user.setdefault("last_login", "")
            user.setdefault("usage", {})
            user["usage"].setdefault("video_total_seconds", 2000)
            user["usage"].setdefault("video_used_seconds", 0)
            user["usage"].setdefault("image_total", 1000)
            user["usage"].setdefault("image_used", 0)
            user["usage"].setdefault("export_total", 164)
            user["usage"].setdefault("export_used", 0)
    if "point_ledger" not in data:
        data["point_ledger"] = []
        for user in data["users"]:
            data["point_ledger"].append(
                {
                    "id": uid("ledger"),
                    "user_id": user["id"],
                    "username": user.get("username"),
                    "display_name": user.get("display_name") or user.get("username"),
                    "amount": int(user.get("points", 0)),
                    "type": "init",
                    "scene": "系统初始化",
                    "description": "兼容旧版本数据时补充初始积分记录",
                    "balance_after": int(user.get("points", 0)),
                    "created_at": now(),
                }
            )
        changed = True
    data.setdefault("usage", {})
    data["usage"].setdefault("video_total_seconds", 2000)
    data["usage"].setdefault("video_used_seconds", 0)
    data["usage"].setdefault("image_total", 1000)
    data["usage"].setdefault("image_used", 0)
    data["usage"].setdefault("export_total", 164)
    data["usage"].setdefault("export_used", 0)
    data["usage"]["team_members"] = len([u for u in data.get("users", []) if u.get("status") == "active"])
    if changed:
        save_data(data)
    return data


def ensure_data_file() -> None:
    if not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(seed_data(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_data() -> dict[str, Any]:
    ensure_data_file()
    with _LOCK:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return normalize_data(data)


def save_data(data: dict[str, Any]) -> None:
    with _LOCK:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot() -> dict[str, Any]:
    return deepcopy(load_data())


def update(mutator):
    data = load_data()
    result = mutator(data)
    save_data(data)
    return result
