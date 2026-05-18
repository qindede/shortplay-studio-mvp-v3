"""drop video_tasks table (merged into ai_jobs)

Revision ID: 20260518_0005
Revises: 20260518_0004
Create Date: 2026-05-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260518_0005"
down_revision = "20260518_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("video_tasks")


def downgrade() -> None:
    op.create_table(
        "video_tasks",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("episode_id", sa.String, sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("shot_id", sa.String, sa.ForeignKey("shots.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ai_job_id", sa.String, sa.ForeignKey("ai_jobs.id"), index=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("duration", sa.Integer, nullable=False),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64)),
        sa.Column("provider_task_id", sa.String(160)),
        sa.Column("preview_url", sa.Text),
        sa.Column("video_url", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_video_tasks_shot_id", "video_tasks", ["shot_id"])
