"""add missing fk indexes

Revision ID: 20260517_0003
Revises: 20260516_0002
Create Date: 2026-05-17
"""
from __future__ import annotations

from alembic import op

revision = "20260517_0003"
down_revision = "20260516_0002"
branch_labels = None
depends_on = None


INDEXES = [
    ("ix_ai_jobs_shot_id", "ai_jobs", ["shot_id"]),
    ("ix_ai_jobs_asset_id", "ai_jobs", ["asset_id"]),
    ("ix_video_tasks_shot_id", "video_tasks", ["shot_id"]),
    ("ix_video_tasks_ai_job_id", "video_tasks", ["ai_job_id"]),
    ("ix_point_ledger_ai_job_id", "point_ledger", ["ai_job_id"]),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
