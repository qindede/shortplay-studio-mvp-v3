"""add lookup indexes

Revision ID: 20260516_0002
Revises: 20260515_0001
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op

revision = "20260516_0002"
down_revision = "20260515_0001"
branch_labels = None
depends_on = None


INDEXES = [
    ("ix_users_token", "users", ["token"]),
    ("ix_projects_owner_user_id", "projects", ["owner_user_id"]),
    ("ix_episodes_project_id", "episodes", ["project_id"]),
    ("ix_shots_episode_id", "shots", ["episode_id"]),
    ("ix_assets_project_id", "assets", ["project_id"]),
    ("ix_asset_references_asset_id", "asset_references", ["asset_id"]),
    ("ix_ai_jobs_user_id", "ai_jobs", ["user_id"]),
    ("ix_ai_jobs_project_id", "ai_jobs", ["project_id"]),
    ("ix_ai_jobs_episode_id", "ai_jobs", ["episode_id"]),
    ("ix_video_tasks_episode_id", "video_tasks", ["episode_id"]),
    ("ix_video_versions_project_id", "video_versions", ["project_id"]),
    ("ix_video_versions_episode_id", "video_versions", ["episode_id"]),
    ("ix_point_ledger_user_id", "point_ledger", ["user_id"]),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
