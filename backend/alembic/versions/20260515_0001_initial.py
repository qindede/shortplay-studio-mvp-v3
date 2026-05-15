"""initial schema

Revision ID: 20260515_0001
Revises:
Create Date: 2026-05-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260515_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token", sa.String(length=256)),
        sa.Column("usage_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("short_name", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cover", sa.String(length=32)),
        sa.Column("cover_image_url", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "episodes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("script", sa.Text()),
        sa.Column("duration_target", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "no"),
    )
    op.create_table(
        "shots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("episode_id", sa.String(), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("visual", sa.Text()),
        sa.Column("dialogue", sa.Text()),
        sa.Column("characters", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("scene", sa.String(length=160)),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("episode_id", "no"),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("initial", sa.String(length=8)),
        sa.Column("image_url", sa.Text()),
        sa.Column("voice_label", sa.String(length=120)),
        sa.Column("voice_url", sa.Text()),
        sa.Column("speaker_id", sa.String(length=120)),
        sa.Column("voice_status", sa.String(length=32)),
        sa.Column("generation_prompt", sa.Text()),
        sa.Column("provider_meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "asset_references",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("asset_id", sa.String(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id")),
        sa.Column("episode_id", sa.String(), sa.ForeignKey("episodes.id")),
        sa.Column("shot_id", sa.String(), sa.ForeignKey("shots.id")),
        sa.Column("asset_id", sa.String(), sa.ForeignKey("assets.id")),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_task_id", sa.String(length=160)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text()),
        sa.Column("cost_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "video_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("episode_id", sa.String(), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_id", sa.String(), sa.ForeignKey("shots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_job_id", sa.String(), sa.ForeignKey("ai_jobs.id")),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64)),
        sa.Column("provider_task_id", sa.String(length=160)),
        sa.Column("preview_url", sa.Text()),
        sa.Column("video_url", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "video_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("ratio", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("theme", sa.String(length=32)),
        sa.Column("preview_url", sa.Text()),
        sa.Column("video_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "point_ledger",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("scene", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("ai_job_id", sa.String(), sa.ForeignKey("ai_jobs.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "point_ledger",
        "video_versions",
        "video_tasks",
        "ai_jobs",
        "asset_references",
        "assets",
        "shots",
        "episodes",
        "projects",
        "users",
    ]:
        op.drop_table(table)
