"""add constraints and composite indexes

Revision ID: 20260518_0004
Revises: 20260517_0003
Create Date: 2026-05-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260518_0004"
down_revision = "20260517_0003"
branch_labels = None
depends_on = None


CHECKS = [
    ("chk_users_role", "users", "role", ("user", "admin")),
    ("chk_users_status", "users", "status", ("active", "disabled")),
    ("chk_shots_status", "shots", "status", ("pending", "generating", "completed", "failed")),
    ("chk_ai_jobs_status", "ai_jobs", "status", ("pending", "running", "succeeded", "failed", "cancelled")),
    ("chk_video_tasks_status", "video_tasks", "status", ("generating", "completed", "failed")),
    ("chk_video_versions_status", "video_versions", "status", ("exported", "archived")),
]

INDEXES = [
    ("ix_point_ledger_user_created", "point_ledger", ["user_id", "created_at"]),
    ("ix_projects_owner_updated", "projects", ["owner_user_id", "updated_at"]),
    ("ix_ai_jobs_project_created", "ai_jobs", ["project_id", "created_at"]),
    ("ix_assets_project_updated", "assets", ["project_id", "updated_at"]),
    ("ix_video_versions_project_created", "video_versions", ["project_id", "created_at"]),
]


def upgrade() -> None:
    for name, table, column, values in CHECKS:
        in_clause = ", ".join(f"'{v}'" for v in values)
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({column} IN ({in_clause}))")

    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)

    op.create_unique_constraint("uq_video_tasks_shot_id", "video_tasks", ["shot_id"])

    op.add_column("projects", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_column("projects", "created_at")
    op.drop_constraint("uq_video_tasks_shot_id", "video_tasks", type_="unique")

    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)

    for name, table, _column, _values in reversed(CHECKS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
