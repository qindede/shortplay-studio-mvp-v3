from __future__ import annotations

import hashlib
import os
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .store import now, snapshot, uid, update

app = FastAPI(title="剧灵 API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_SECRET = os.getenv("SHORTPLAY_AUTH_SECRET", "shortplay-mvp-secret")

POINT_RULES = {
    "outline": 20,
    "storyboard": 10,
    "video_second": 10,
    "image_asset": 20,
    "audio_asset": 5,
    "compose": 30,
}


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    display_name: str = Field(default="", max_length=32)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class EpisodeDraft(BaseModel):
    title: str = Field(min_length=1)
    summary: str = ""
    script: str = ""
    duration_target: int = Field(default=30, ge=5, le=300)


class OutlineGenerateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    episode_count: int = Field(default=6, ge=3, le=24)


class OutlineGenerateResponse(BaseModel):
    cost: int
    episodes: list[EpisodeDraft]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    owner: str = "未分配"
    episodes: list[EpisodeDraft] = Field(default_factory=list)


class EpisodeCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str = ""
    script: str = ""
    duration_target: int = 30


class EpisodeUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    script: str | None = None
    duration_target: int | None = None
    status: str | None = None


class AssetCreate(BaseModel):
    type: str = Field(pattern="^(character|scene|image|audio)$")
    name: str = Field(min_length=1)
    description: str = ""
    initial: str = "素"


class ShotUpdate(BaseModel):
    title: str | None = None
    visual: str | None = None
    dialogue: str | None = None
    characters: list[str] | None = None
    scene: str | None = None
    duration: int | None = None
    status: str | None = None


class ComposeRequest(BaseModel):
    name: str = "成片版本"
    description: str = "合成生成"
    ratio: str = "9:16"
    duration: int = 30


class AdminPointAdjust(BaseModel):
    amount: int = Field(description="正数为充值，负数为扣减")
    reason: str = "管理员调整"


class AdminUserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(user|admin)$")
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


STATUS_LABEL = {
    "active": "制作中",
    "review": "待审核",
    "draft": "草稿",
    "completed": "已完成",
    "storyboard_ready": "已生成",
    "generating": "生成中",
    "pending": "待生成",
    "needs_review": "待优化",
    "exported": "已导出",
}


def hash_password(password: str) -> str:
    return hashlib.sha256(f"{AUTH_SECRET}:{password}".encode("utf-8")).hexdigest()


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name") or user["username"],
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
        "points": int(user.get("points", 0)),
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login"),
    }


def not_found(name: str):
    raise HTTPException(status_code=404, detail=f"{name} not found")


def find_user_by_token(data: dict, token: str | None) -> dict | None:
    if not token:
        return None
    return next((u for u in data.get("users", []) if u.get("token") == token), None)


def get_current_user(x_user_token: Annotated[str | None, Header(alias="X-User-Token")] = None) -> dict:
    data = snapshot()
    user = find_user_by_token(data, x_user_token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return public_user(user)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def user_in_data(data: dict, user_id: str) -> dict:
    user = next((u for u in data.get("users", []) if u["id"] == user_id), None)
    if not user:
        not_found("user")
    return user


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
    episodes = [e for e in data["episodes"] if e["project_id"] == project["id"]]
    assets = [a for a in data["assets"] if a["project_id"] == project["id"]]
    versions = [v for v in data["video_versions"] if v["project_id"] == project["id"]]
    return {
        **project,
        "status_label": STATUS_LABEL.get(project.get("status"), project.get("status")),
        "episode_count": len(episodes),
        "asset_count": len(assets),
        "version_count": len(versions),
    }


def enrich_episode(data: dict, episode: dict) -> dict:
    shots = [s for s in data["shots"] if s["episode_id"] == episode["id"]]
    versions = [v for v in data["video_versions"] if v["episode_id"] == episode["id"]]
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


@app.get("/api/health")
def health():
    return {"ok": True, "name": "剧灵"}


@app.post("/api/auth/register")
def register(payload: RegisterRequest):
    username = payload.username.strip().lower()
    display_name = payload.display_name.strip() or username

    def mutate(data):
        if any(u["username"].lower() == username for u in data.get("users", [])):
            raise HTTPException(status_code=409, detail="用户名已存在")
        user = {
            "id": uid("user"),
            "username": username,
            "display_name": display_name,
            "password_hash": hash_password(payload.password),
            "role": "user",
            "status": "active",
            "points": 0,
            "token": secrets.token_urlsafe(24),
            "created_at": now(),
            "last_login": now(),
        }
        data.setdefault("users", []).append(user)
        change_points(data, user["id"], 1000, "register_bonus", "注册赠送", "新用户注册赠送积分")
        return {"user": public_user(user), "token": user["token"]}

    return update(mutate)


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    username = payload.username.strip().lower()

    def mutate(data):
        user = next((u for u in data.get("users", []) if u["username"].lower() == username), None)
        if not user or user.get("password_hash") != hash_password(payload.password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if user.get("status") != "active":
            raise HTTPException(status_code=403, detail="账号已被禁用")
        user["token"] = secrets.token_urlsafe(24)
        user["last_login"] = now()
        return {"user": public_user(user), "token": user["token"]}

    return update(mutate)


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/api/me/point-ledger")
def my_point_ledger(user: dict = Depends(get_current_user)):
    data = snapshot()
    return [e for e in data.get("point_ledger", []) if e["user_id"] == user["id"]][:100]


@app.get("/api/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    data = snapshot()
    return {
        "project_count": len(data["projects"]),
        "episode_count": len(data["episodes"]),
        "version_count": len(data["video_versions"]),
        "asset_count": len(data["assets"]),
        "usage": usage_with_members(data),
        "current_user": user,
    }


@app.get("/api/projects")
def list_projects(user: dict = Depends(get_current_user)):
    data = snapshot()
    return [enrich_project(data, p) for p in data["projects"]]


@app.post("/api/projects")
def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
    def mutate(data):
        project = {
            "id": uid("proj"),
            "name": payload.name,
            "short_name": payload.name[:8],
            "description": payload.description,
            "status": "draft",
            "owner": payload.owner if payload.owner != "未分配" else user["display_name"],
            "owner_user_id": user["id"],
            "cover": "dark",
            "updated_at": now(),
        }
        data["projects"].insert(0, project)
        for index, item in enumerate(payload.episodes, start=1):
            data["episodes"].append(
                {
                    "id": uid("ep"),
                    "project_id": project["id"],
                    "no": index,
                    "title": item.title,
                    "summary": item.summary,
                    "script": item.script or item.summary,
                    "duration_target": item.duration_target,
                    "status": "draft",
                    "updated_at": now(),
                }
            )
        return enrich_project(data, project)

    return update(mutate)


def build_project_outline(payload: OutlineGenerateRequest) -> list[EpisodeDraft]:
    name = payload.name.strip()
    description = payload.description.strip()
    beats = [
        ("强钩子开场", "用最强冲突打开故事，主角被迫进入无法回头的局面。"),
        ("误会升级", "核心人物互相试探，隐藏身份或关键秘密被第一次触碰。"),
        ("反派施压", "对手主动出击，主角的目标、尊严或关系受到明显威胁。"),
        ("关键反转", "主角拿到新线索，局势从被动挨打转向主动布局。"),
        ("情感裂痕", "最重要的关系出现误解，短剧的情绪张力被推高。"),
        ("证据浮出", "真相碎片被串联起来，观众看到下一轮爆点的入口。"),
        ("当众打脸", "主角在公开场合完成一次强反击，爽点集中释放。"),
        ("身份揭露", "核心身份或幕后关系被揭开，人物站位发生变化。"),
        ("终局逼近", "反派孤注一掷，主角必须在有限时间内做选择。"),
        ("高潮收束", "主角完成最终反转，并给下一季或番外留下余味。"),
    ]
    episodes: list[EpisodeDraft] = []
    for index in range(payload.episode_count):
        beat_title, beat_summary = beats[index % len(beats)]
        title = beat_title
        summary = f"{description} 本集聚焦“{beat_title}”：{beat_summary}"
        script = (
            f"项目《{name}》第{index + 1}集。"
            f"剧情摘要：{summary} "
            "建议用开场三秒冲突、人物对峙、结尾悬念组织脚本。"
        )
        episodes.append(EpisodeDraft(title=title, summary=summary, script=script, duration_target=30))
    return episodes


@app.post("/api/projects/generate-outline", response_model=OutlineGenerateResponse)
def generate_project_outline(payload: OutlineGenerateRequest, user: dict = Depends(get_current_user)):
    def mutate(data):
        cost = POINT_RULES["outline"]
        change_points(data, user["id"], -cost, "consume", "生成短剧大纲", f"智能生成《{payload.name}》短剧大纲")
        return {"cost": cost, "episodes": build_project_outline(payload)}

    return update(mutate)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    project = next((p for p in data["projects"] if p["id"] == project_id), None)
    if not project:
        not_found("project")
    return enrich_project(data, project)


@app.get("/api/projects/{project_id}/episodes")
def list_episodes(project_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    if not any(p["id"] == project_id for p in data["projects"]):
        not_found("project")
    episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
    episodes.sort(key=lambda x: x["no"])
    return [enrich_episode(data, e) for e in episodes]


@app.post("/api/projects/{project_id}/episodes")
def create_episode(project_id: str, payload: EpisodeCreate, user: dict = Depends(get_current_user)):
    def mutate(data):
        if not any(p["id"] == project_id for p in data["projects"]):
            not_found("project")
        project_episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
        episode = {
            "id": uid("ep"),
            "project_id": project_id,
            "no": max([e["no"] for e in project_episodes] or [0]) + 1,
            "title": payload.title,
            "summary": payload.summary,
            "script": payload.script,
            "duration_target": payload.duration_target,
            "status": "draft",
            "updated_at": now(),
        }
        data["episodes"].append(episode)
        return enrich_episode(data, episode)

    return update(mutate)


@app.get("/api/episodes/{episode_id}")
def get_episode(episode_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
    if not episode:
        not_found("episode")
    return enrich_episode(data, episode)


@app.put("/api/episodes/{episode_id}")
def update_episode(episode_id: str, payload: EpisodeUpdate, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
        if not episode:
            not_found("episode")
        for key, value in payload.model_dump(exclude_none=True).items():
            episode[key] = value
        episode["updated_at"] = now()
        return enrich_episode(data, episode)

    return update(mutate)


@app.delete("/api/episodes/{episode_id}")
def delete_episode(episode_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
        if not episode:
            not_found("episode")

        project_id = episode["project_id"]
        data["episodes"] = [e for e in data["episodes"] if e["id"] != episode_id]
        data["shots"] = [s for s in data["shots"] if s["episode_id"] != episode_id]
        data["video_tasks"] = [t for t in data["video_tasks"] if t["episode_id"] != episode_id]
        data["video_versions"] = [v for v in data["video_versions"] if v["episode_id"] != episode_id]

        project_episodes = [e for e in data["episodes"] if e["project_id"] == project_id]
        project_episodes.sort(key=lambda item: item["no"])
        for index, item in enumerate(project_episodes, start=1):
            item["no"] = index

        project = next((p for p in data["projects"] if p["id"] == project_id), None)
        if project:
            project["updated_at"] = now()

        return {"ok": True}

    return update(mutate)


@app.get("/api/episodes/{episode_id}/shots")
def list_shots(episode_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
    shots.sort(key=lambda x: x["no"])
    return shots


def build_storyboard(episode: dict) -> list[dict]:
    scene = "豪门宴会厅"
    base = [
        ("冲突进入", "主角突然进入关键场景，所有人的视线集中到她身上。", "这件事，不能就这样结束。", ["林晚"], 3),
        ("当众质疑", "反派和围观者形成压力，现场气氛迅速变紧张。", "她是谁？凭什么出现在这里？", ["苏晴"], 4),
        ("关键人物起身", "男主从人群中起身，镜头缓慢推进，现场安静下来。", "", ["顾沉"], 5),
        ("身份反转", "男主站到女主身边，公开给出决定性信息，众人震惊。", "她才是我真正要保护的人。", ["林晚", "顾沉"], 6),
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


@app.post("/api/episodes/{episode_id}/generate-storyboard")
def generate_storyboard(episode_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
        if not episode:
            not_found("episode")
        change_points(data, user["id"], -POINT_RULES["storyboard"], "consume", "生成分镜", f"生成/更新《{episode['title']}》分镜")
        data["shots"] = [s for s in data["shots"] if s["episode_id"] != episode_id]
        new_shots = build_storyboard(episode)
        data["shots"].extend(new_shots)
        episode["status"] = "storyboard_ready"
        episode["updated_at"] = now()
        return new_shots

    return update(mutate)


@app.patch("/api/shots/{shot_id}")
def patch_shot(shot_id: str, payload: ShotUpdate, user: dict = Depends(get_current_user)):
    def mutate(data):
        shot = next((s for s in data["shots"] if s["id"] == shot_id), None)
        if not shot:
            not_found("shot")
        updates = payload.model_dump(exclude_none=True)
        for key, value in updates.items():
            shot[key] = value
        shot["updated_at"] = now()

        task = next((t for t in data["video_tasks"] if t["shot_id"] == shot_id), None)
        if task:
            if "title" in updates:
                task["title"] = shot["title"]
            if "duration" in updates:
                task["duration"] = shot["duration"]
            task["updated_at"] = now()

        episode = next((e for e in data["episodes"] if e["id"] == shot["episode_id"]), None)
        if episode:
            episode["updated_at"] = now()
            project = next((p for p in data["projects"] if p["id"] == episode["project_id"]), None)
            if project:
                project["updated_at"] = episode["updated_at"]
        return shot

    return update(mutate)


@app.delete("/api/shots/{shot_id}")
def delete_shot(shot_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        shot = next((s for s in data["shots"] if s["id"] == shot_id), None)
        if not shot:
            not_found("shot")

        episode_id = shot["episode_id"]
        data["shots"] = [s for s in data["shots"] if s["id"] != shot_id]
        data["video_tasks"] = [t for t in data["video_tasks"] if t["shot_id"] != shot_id]

        episode_shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        episode_shots.sort(key=lambda item: item["no"])
        for index, item in enumerate(episode_shots, start=1):
            item["no"] = index

        episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
        if episode:
            episode["updated_at"] = now()
            project = next((p for p in data["projects"] if p["id"] == episode["project_id"]), None)
            if project:
                project["updated_at"] = episode["updated_at"]

        return {"ok": True}

    return update(mutate)


@app.get("/api/episodes/{episode_id}/video-tasks")
def list_video_tasks(episode_id: str, user: dict = Depends(get_current_user)):
    data = snapshot()
    tasks = [t for t in data["video_tasks"] if t["episode_id"] == episode_id]
    tasks.sort(key=lambda x: x["updated_at"], reverse=True)
    return tasks


@app.post("/api/shots/{shot_id}/generate-video")
def generate_video_for_shot(shot_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        shot = next((s for s in data["shots"] if s["id"] == shot_id), None)
        if not shot:
            not_found("shot")
        cost = max(1, int(shot["duration"])) * POINT_RULES["video_second"]
        change_points(data, user["id"], -cost, "consume", "生成镜头视频", f"生成镜头 #{shot['no']}《{shot['title']}》，{shot['duration']}s")
        task = next((t for t in data["video_tasks"] if t["shot_id"] == shot_id), None)
        if not task:
            task = {
                "id": uid("task"),
                "episode_id": shot["episode_id"],
                "shot_id": shot_id,
                "title": shot["title"],
                "duration": shot["duration"],
                "progress": 100,
                "status": "completed",
                "updated_at": now(),
            }
            data["video_tasks"].append(task)
        else:
            task.update({"progress": 100, "status": "completed", "updated_at": now()})
        shot["status"] = "completed"
        shot["updated_at"] = now()
        usage = data["usage"]
        usage["video_used_seconds"] = min(usage["video_total_seconds"], usage["video_used_seconds"] + shot["duration"])
        return task

    return update(mutate)


@app.post("/api/episodes/{episode_id}/generate-videos")
def generate_all_videos(episode_id: str, user: dict = Depends(get_current_user)):
    def mutate(data):
        shots = [s for s in data["shots"] if s["episode_id"] == episode_id]
        if not shots:
            not_found("shots")
        episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
        total_duration = sum(max(1, int(s["duration"])) for s in shots)
        cost = total_duration * POINT_RULES["video_second"]
        change_points(data, user["id"], -cost, "consume", "批量生成视频", f"批量生成《{episode['title'] if episode else episode_id}》{len(shots)}个镜头，{total_duration}s")
        created = []
        for shot in shots:
            task = next((t for t in data["video_tasks"] if t["shot_id"] == shot["id"]), None)
            if not task:
                task = {
                    "id": uid("task"),
                    "episode_id": episode_id,
                    "shot_id": shot["id"],
                    "title": shot["title"],
                    "duration": shot["duration"],
                    "progress": 100,
                    "status": "completed",
                    "updated_at": now(),
                }
                data["video_tasks"].append(task)
            else:
                task.update({"progress": 100, "status": "completed", "updated_at": now()})
            shot["status"] = "completed"
            shot["updated_at"] = now()
            created.append(task)
        if episode:
            episode["status"] = "completed"
            episode["updated_at"] = now()
        usage = data["usage"]
        usage["video_used_seconds"] = min(usage["video_total_seconds"], usage["video_used_seconds"] + total_duration)
        return created

    return update(mutate)


@app.get("/api/projects/{project_id}/assets")
def list_assets(project_id: str, type: str | None = None, user: dict = Depends(get_current_user)):
    data = snapshot()
    assets = [a for a in data["assets"] if a["project_id"] == project_id]
    if type:
        assets = [a for a in assets if a["type"] == type]
    return assets


@app.post("/api/projects/{project_id}/assets")
def create_asset(project_id: str, payload: AssetCreate, user: dict = Depends(get_current_user)):
    def mutate(data):
        if not any(p["id"] == project_id for p in data["projects"]):
            not_found("project")
        if payload.type in {"character", "scene", "image"}:
            cost = POINT_RULES["image_asset"]
            scene = "创建视觉素材"
        else:
            cost = POINT_RULES["audio_asset"]
            scene = "创建音频素材"
        change_points(data, user["id"], -cost, "consume", scene, f"创建素材《{payload.name}》")
        asset = {
            "id": uid("asset"),
            "project_id": project_id,
            "type": payload.type,
            "name": payload.name,
            "description": payload.description,
            "ref_count": 0,
            "initial": payload.initial[:1] or payload.name[:1],
            "updated_at": now(),
        }
        data["assets"].insert(0, asset)
        if payload.type in {"character", "scene", "image"}:
            data["usage"]["image_used"] = min(data["usage"]["image_total"], data["usage"]["image_used"] + 1)
        return asset

    return update(mutate)


@app.get("/api/projects/{project_id}/video-versions")
def list_video_versions(project_id: str, episode_id: str | None = None, user: dict = Depends(get_current_user)):
    data = snapshot()
    versions = [v for v in data["video_versions"] if v["project_id"] == project_id]
    if episode_id:
        versions = [v for v in versions if v["episode_id"] == episode_id]
    versions.sort(key=lambda x: x["created_at"], reverse=True)
    return versions


@app.post("/api/episodes/{episode_id}/compose")
def compose_episode(episode_id: str, payload: ComposeRequest, user: dict = Depends(get_current_user)):
    def mutate(data):
        episode = next((e for e in data["episodes"] if e["id"] == episode_id), None)
        if not episode:
            not_found("episode")
        change_points(data, user["id"], -POINT_RULES["compose"], "consume", "合成成片", f"合成《{episode['title']}》成片版本")
        version_no = len([v for v in data["video_versions"] if v["episode_id"] == episode_id]) + 1
        version = {
            "id": uid("ver"),
            "project_id": episode["project_id"],
            "episode_id": episode_id,
            "name": payload.name if payload.name != "成片版本" else f"第{episode['no']:02d}集 版本{chr(64 + version_no)}",
            "description": payload.description,
            "duration": payload.duration,
            "ratio": payload.ratio,
            "status": "review",
            "theme": "green" if version_no % 2 else "blue",
            "created_at": now(),
        }
        data["video_versions"].insert(0, version)
        data["usage"]["export_used"] = min(data["usage"]["export_total"], data["usage"]["export_used"] + 1)
        return version

    return update(mutate)


@app.get("/api/usage")
def usage(user: dict = Depends(get_current_user)):
    data = snapshot()
    return usage_with_members(data)


@app.get("/api/point-rules")
def point_rules(user: dict = Depends(get_current_user)):
    return POINT_RULES


@app.get("/api/admin/summary")
def admin_summary(admin: dict = Depends(require_admin)):
    data = snapshot()
    users = data.get("users", [])
    ledger = data.get("point_ledger", [])
    consumed = -sum(e["amount"] for e in ledger if e["amount"] < 0)
    granted = sum(e["amount"] for e in ledger if e["amount"] > 0)
    return {
        "user_count": len(users),
        "active_user_count": len([u for u in users if u.get("status") == "active"]),
        "total_balance": sum(int(u.get("points", 0)) for u in users),
        "consumed_points": consumed,
        "granted_points": granted,
        "ledger_count": len(ledger),
    }


@app.get("/api/admin/users")
def admin_users(admin: dict = Depends(require_admin)):
    data = snapshot()
    return [public_user(u) for u in data.get("users", [])]


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, payload: AdminUserUpdate, admin: dict = Depends(require_admin)):
    def mutate(data):
        target = user_in_data(data, user_id)
        if payload.role is not None:
            target["role"] = payload.role
        if payload.status is not None:
            target["status"] = payload.status
        return public_user(target)

    return update(mutate)


@app.post("/api/admin/users/{user_id}/points")
def admin_adjust_points(user_id: str, payload: AdminPointAdjust, admin: dict = Depends(require_admin)):
    if payload.amount == 0:
        raise HTTPException(status_code=400, detail="调整积分不能为 0")

    def mutate(data):
        entry = change_points(data, user_id, payload.amount, "admin_adjust", "管理员调整", payload.reason)
        return {"entry": entry, "user": public_user(user_in_data(data, user_id))}

    return update(mutate)


@app.get("/api/admin/point-ledger")
def admin_point_ledger(user_id: str | None = Query(default=None), admin: dict = Depends(require_admin)):
    data = snapshot()
    rows = data.get("point_ledger", [])
    if user_id:
        rows = [r for r in rows if r["user_id"] == user_id]
    return rows[:200]
