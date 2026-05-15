from __future__ import annotations

from pydantic import BaseModel, Field


class OutlineEpisode(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(default="", max_length=1000)
    script: str = Field(default="", max_length=8000)
    duration_target: int = Field(default=30, ge=5, le=300)


class OutlineResult(BaseModel):
    episodes: list[OutlineEpisode] = Field(min_length=1)


class StoryboardShot(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    visual: str = Field(default="", max_length=2000)
    dialogue: str = Field(default="", max_length=2000)
    characters: list[str] = Field(default_factory=list)
    scene: str = Field(default="", max_length=120)
    duration: int = Field(default=3, ge=1, le=60)


class StoryboardResult(BaseModel):
    shots: list[StoryboardShot] = Field(min_length=1)
