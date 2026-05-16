from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import db_store
from .config import DEFAULT_USAGE
from .security import hash_password as default_password_hash
from .seed_data import seed_data
from .utils import now, uid

DATA_PATH = Path(os.getenv("SHORTPLAY_DB", Path(__file__).resolve().parent.parent / "data" / "db.json"))
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
_LOCK = threading.Lock()


def default_users() -> list[dict[str, Any]]:
    ts = now()
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
            "usage": {**DEFAULT_USAGE},
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
            "usage": {**DEFAULT_USAGE},
            "created_at": ts,
            "last_login": "",
        },
    ]



def normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    changed = False
    # Migrate projects without owner_user_id - assign to admin
    for project in data.get("projects", []):
        if "owner_user_id" not in project:
            project["owner_user_id"] = "user_admin"
            changed = True
    # Migrate cover_image field on projects
    _cover_image_map = {
        "proj_haomen": "/covers/haomen.jpg",
        "proj_qianjin": "/covers/qianjin.jpg",
        "proj_zhuixu": "/covers/zhuixu.jpg",
        "proj_rebirth": "/covers/rebirth.jpg",
    }
    for project in data.get("projects", []):
        if "cover_image" not in project and project["id"] in _cover_image_map:
            project["cover_image"] = _cover_image_map[project["id"]]
            changed = True
    # Migrate image field on assets
    _asset_image_map = {
        "asset_linwan": "/portraits/linwan.jpg",
        "asset_guchen": "/portraits/guchen.jpg",
        "asset_suqing": "/portraits/suqing.jpg",
        "asset_banquet": "/scenes/banquet.jpg",
        "asset_hospital": "/scenes/hospital.jpg",
        "asset_bairuoxue": "/portraits/bairuoxue.jpg",
        "asset_lujiinian": "/portraits/lujiinian.jpg",
        "asset_zhouzixuan": "/portraits/zhouzixuan.jpg",
        "asset_scene_hospital": "/scenes/hospital.jpg",
        "asset_scene_villa": "/scenes/villa.jpg",
        "asset_scene_office": "/scenes/office.jpg",
        "asset_scene_rooftop": "/scenes/rooftop.jpg",
    }
    for asset in data.get("assets", []):
        if "image" not in asset and asset["id"] in _asset_image_map:
            asset["image"] = _asset_image_map[asset["id"]]
            changed = True
    # Migrate multi-reference assets for the detail gallery.
    _asset_reference_sources = {
        "asset_linwan": ["/portraits/linwan.jpg", "/images/poster.jpg", "/scenes/banquet.jpg"],
        "asset_guchen": ["/portraits/guchen.jpg", "/scenes/banquet.jpg", "/scenes/office.jpg"],
        "asset_suqing": ["/portraits/suqing.jpg", "/scenes/banquet.jpg", "/images/poster.jpg"],
        "asset_banquet": ["/scenes/banquet.jpg", "/images/poster.jpg", "/scenes/villa.jpg"],
        "asset_hospital": ["/scenes/hospital.jpg", "/portraits/bairuoxue.jpg", "/scenes/office.jpg"],
        "asset_img_poster": ["/images/poster.jpg", "/portraits/linwan.jpg"],
        "asset_bairuoxue": ["/portraits/bairuoxue.jpg", "/scenes/hospital.jpg", "/images/poster.jpg"],
        "asset_lujiinian": ["/portraits/lujiinian.jpg", "/scenes/villa.jpg", "/scenes/office.jpg"],
        "asset_zhouzixuan": ["/portraits/zhouzixuan.jpg", "/scenes/villa.jpg", "/images/poster.jpg"],
        "asset_scene_hospital": ["/scenes/hospital.jpg", "/portraits/bairuoxue.jpg"],
        "asset_scene_villa": ["/scenes/villa.jpg", "/portraits/lujiinian.jpg"],
        "asset_scene_office": ["/scenes/office.jpg", "/scenes/rooftop.jpg"],
        "asset_scene_rooftop": ["/scenes/rooftop.jpg", "/scenes/office.jpg"],
    }
    for asset in data.get("assets", []):
        if "references" not in asset:
            sources = _asset_reference_sources.get(asset["id"], [])
            if sources:
                asset["references"] = [
                    {
                        "id": f'{asset["id"]}_ref_{index + 1}',
                        "type": "image",
                        "name": f'参考图 {index + 1}',
                        "url": source,
                        "note": asset.get("description", ""),
                    }
                    for index, source in enumerate(sources)
                ]
                asset["ref_count"] = max(int(asset.get("ref_count", 0)), len(sources))
            else:
                asset["references"] = []
            changed = True
    # Migrate voice and voice_url fields on character assets
    _asset_voice_map = {
        "asset_linwan": ("温柔清冷女声", "/voices/linwan.wav"),
        "asset_guchen": ("低沉磁性男声", "/voices/guchen.wav"),
        "asset_suqing": ("甜美傲娇女声", "/voices/suqing.wav"),
        "asset_bairuoxue": ("柔美温婉女声", "/voices/bairuoxue.wav"),
        "asset_lujiinian": ("沉稳内敛男声", "/voices/lujiinian.wav"),
        "asset_zhouzixuan": ("嚣张傲慢男声", "/voices/zhouzixuan.wav"),
    }
    for asset in data.get("assets", []):
        if asset.get("type") == "character" and "voice" not in asset:
            voice_info = _asset_voice_map.get(asset["id"])
            if voice_info:
                asset["voice"] = voice_info[0]
                asset["voice_url"] = voice_info[1]
            else:
                asset["voice"] = None
                asset["voice_url"] = None
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
            for key, value in DEFAULT_USAGE.items():
                user["usage"].setdefault(key, value)
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
    for key, value in DEFAULT_USAGE.items():
        data["usage"].setdefault(key, value)
    data["usage"]["team_members"] = len([u for u in data.get("users", []) if u.get("status") == "active"])
    if changed:
        save_data(data)
    return data


def ensure_data_file() -> None:
    if not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(seed_data(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_data() -> dict[str, Any]:
    if db_store.enabled():
        data = db_store.load_data()
        if not data.get("users") and not data.get("projects"):
            data = seed_data()
            db_store.save_data(data)
        return normalize_data(data)

    ensure_data_file()
    with _LOCK:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return normalize_data(data)


def save_data(data: dict[str, Any]) -> None:
    if db_store.enabled():
        db_store.save_data(data)
        return

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
