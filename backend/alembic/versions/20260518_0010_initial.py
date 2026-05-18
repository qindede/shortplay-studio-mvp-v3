"""initial schema (squashed)

Squashes 20260515_0001 through 20260518_0005 into a single migration.
video_tasks table removed (merged into ai_jobs).

Revision ID: 20260518_0010
Revises:
Create Date: 2026-05-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260518_0010"
down_revision = None
branch_labels = None
depends_on = None


CHECKS = [
    ("chk_users_role", "users", "role", ("user", "admin")),
    ("chk_users_status", "users", "status", ("active", "disabled")),
    ("chk_shots_status", "shots", "status", ("pending", "generating", "completed", "failed")),
    ("chk_ai_jobs_status", "ai_jobs", "status", ("pending", "running", "succeeded", "failed", "cancelled")),
    ("chk_ai_jobs_type", "ai_jobs", "type", ("outline", "storyboard", "image_asset", "audio_asset", "video_shot", "compose", "voice_clone")),
    ("chk_assets_type", "assets", "type", ("character", "scene", "image", "audio")),
    ("chk_assets_voice_status", "assets", "voice_status", ("uploaded", "pending", "generating", "completed", "failed")),
    ("chk_asset_references_type", "asset_references", "type", ("image", "audio")),
    ("chk_point_ledger_type", "point_ledger", "type", ("init", "register_bonus", "consume", "refund", "admin_adjust")),
    ("chk_video_versions_status", "video_versions", "status", ("exported", "archived")),
]

# Complex CHECK constraints that can't be expressed as simple IN lists
RAW_CHECKS = [
    # AiJob type → required FK
    ("chk_ai_jobs_fk_video_shot", "ai_jobs", "type <> 'video_shot' OR (shot_id IS NOT NULL AND episode_id IS NOT NULL)"),
    ("chk_ai_jobs_fk_compose", "ai_jobs", "type <> 'compose' OR episode_id IS NOT NULL"),
    ("chk_ai_jobs_fk_storyboard", "ai_jobs", "type <> 'storyboard' OR episode_id IS NOT NULL"),
    # image_asset / audio_asset: asset_id is set AFTER job creation (asset created inside work()),
    # so no FK constraint here — the job starts with asset_id=NULL.
    ("chk_ai_jobs_fk_voice_clone", "ai_jobs", "type <> 'voice_clone' OR asset_id IS NOT NULL"),
]

SINGLE_INDEXES = [
    ("ix_users_token", "users", ["token"]),
    ("ix_projects_owner_user_id", "projects", ["owner_user_id"]),
    ("ix_episodes_project_id", "episodes", ["project_id"]),
    ("ix_shots_episode_id", "shots", ["episode_id"]),
    ("ix_assets_project_id", "assets", ["project_id"]),
    ("ix_asset_references_asset_id", "asset_references", ["asset_id"]),
    ("ix_ai_jobs_user_id", "ai_jobs", ["user_id"]),
    ("ix_ai_jobs_project_id", "ai_jobs", ["project_id"]),
    ("ix_ai_jobs_episode_id", "ai_jobs", ["episode_id"]),
    ("ix_ai_jobs_shot_id", "ai_jobs", ["shot_id"]),
    ("ix_ai_jobs_asset_id", "ai_jobs", ["asset_id"]),
    ("ix_video_versions_project_id", "video_versions", ["project_id"]),
    ("ix_video_versions_episode_id", "video_versions", ["episode_id"]),
    ("ix_point_ledger_user_id", "point_ledger", ["user_id"]),
    ("ix_point_ledger_ai_job_id", "point_ledger", ["ai_job_id"]),
]

COMPOSITE_INDEXES = [
    ("ix_point_ledger_user_created", "point_ledger", ["user_id", "created_at"]),
    ("ix_projects_owner_updated", "projects", ["owner_user_id", "updated_at"]),
    ("ix_ai_jobs_project_created", "ai_jobs", ["project_id", "created_at"]),
    ("ix_assets_project_updated", "assets", ["project_id", "updated_at"]),
    ("ix_video_versions_project_created", "video_versions", ["project_id", "created_at"]),
]


def upgrade() -> None:
    # --- tables ---
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
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

    # --- single-column indexes ---
    for name, table, columns in SINGLE_INDEXES:
        op.create_index(name, table, columns)

    # --- composite indexes ---
    for name, table, columns in COMPOSITE_INDEXES:
        op.create_index(name, table, columns)

    # --- check constraints ---
    for name, table, column, values in CHECKS:
        in_clause = ", ".join(f"'{v}'" for v in values)
        # voice_status is nullable; allow NULL alongside the IN list
        if column == "voice_status":
            op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({column} IS NULL OR {column} IN ({in_clause}))")
        else:
            op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({column} IN ({in_clause}))")

    for name, table, expr in RAW_CHECKS:
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expr})")


def downgrade() -> None:
    for name, table, _expr in reversed(RAW_CHECKS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")

    for name, table, _column, _values in reversed(CHECKS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")

    for name, table, _columns in reversed(COMPOSITE_INDEXES):
        op.drop_index(name, table_name=table)

    for name, table, _columns in reversed(SINGLE_INDEXES):
        op.drop_index(name, table_name=table)

    for table in [
        "point_ledger",
        "video_versions",
        "ai_jobs",
        "asset_references",
        "assets",
        "shots",
        "episodes",
        "projects",
        "users",
    ]:
        op.drop_table(table)
