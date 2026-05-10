from __future__ import annotations

from pydantic import BaseModel, Field


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
    duration_target: int = Field(default=30, ge=1, le=300)


class EpisodeUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    script: str | None = None
    duration_target: int | None = Field(default=None, ge=1, le=300)
    status: str | None = None


class AssetCreate(BaseModel):
    type: str = Field(pattern="^(character|scene|image|audio)$")
    name: str = Field(min_length=1)
    description: str = ""
    initial: str = "素"


class ShotCreate(BaseModel):
    title: str = Field(min_length=1)
    visual: str = ""
    dialogue: str = ""
    characters: list[str] = Field(default_factory=list)
    scene: str = ""
    duration: int = Field(default=3, ge=1, le=60)


class ShotUpdate(BaseModel):
    title: str | None = None
    visual: str | None = None
    dialogue: str | None = None
    characters: list[str] | None = None
    scene: str | None = None
    duration: int | None = Field(default=None, ge=1, le=60)


class ComposeRequest(BaseModel):
    name: str = "成片版本"
    description: str = "合成生成"
    ratio: str = "9:16"
    duration: int = Field(default=30, ge=1, le=600)


class AdminPointAdjust(BaseModel):
    amount: int = Field(description="正数为充值，负数为扣减")
    reason: str = "管理员调整"


class AdminUserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(user|admin)$")
    status: str | None = Field(default=None, pattern="^(active|disabled)$")
