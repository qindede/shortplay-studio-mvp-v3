"""Workspace — 聚合读模型。

本模块允许直接 join 多个表来构建前端所需的聚合视图；
但不调用其他 feature 的 db/queries，也不做写操作。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ...config import apply_usage_defaults, STATUS_LABEL
from ...db import SessionLocal, require_db
from ...utils import fmt_dt


@require_db
def workspace_bootstrap(user: dict[str, Any]) -> dict[str, Any]:

    with SessionLocal() as db:
        usage = apply_usage_defaults({**(user.get("usage") or {})})
        row = db.execute(
            text(
                """
                WITH user_projects AS (
                    SELECT *
                    FROM projects
                    WHERE owner_user_id = :user_id
                ),
                first_project AS (
                    SELECT id
                    FROM user_projects
                    ORDER BY updated_at DESC
                    LIMIT 1
                ),
                first_episodes AS (
                    SELECT e.*
                    FROM episodes e
                    JOIN first_project fp ON fp.id = e.project_id
                ),
                first_episode AS (
                    SELECT id
                    FROM first_episodes
                    ORDER BY no
                    LIMIT 1
                )
                SELECT
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', p.id,
                                'owner_user_id', p.owner_user_id,
                                'owner', CAST(:display_name AS text),
                                'name', p.name,
                                'short_name', p.short_name,
                                'description', COALESCE(p.description, ''),
                                'status', p.status,
                                'cover', p.cover,
                                'cover_image', p.cover_image_url,
                                'updated_at', p.updated_at,
                                'episode_count', (SELECT count(*) FROM episodes e WHERE e.project_id = p.id),
                                'asset_count', (SELECT count(*) FROM assets a WHERE a.project_id = p.id),
                                'version_count', (SELECT count(*) FROM video_versions v WHERE v.project_id = p.id)
                            )
                            ORDER BY p.updated_at DESC
                        )
                        FROM user_projects p
                    ), '[]'::jsonb) AS projects,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', e.id,
                                'project_id', e.project_id,
                                'no', e.no,
                                'title', e.title,
                                'summary', COALESCE(e.summary, ''),
                                'script', COALESCE(e.script, ''),
                                'duration_target', e.duration_target,
                                'status', e.status,
                                'updated_at', e.updated_at,
                                'shot_count', (SELECT count(*) FROM shots s WHERE s.episode_id = e.id),
                                'version_count', (SELECT count(*) FROM video_versions v WHERE v.episode_id = e.id)
                            )
                            ORDER BY e.no
                        )
                        FROM first_episodes e
                    ), '[]'::jsonb) AS episodes,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', a.id,
                                'project_id', a.project_id,
                                'type', a.type,
                                'name', a.name,
                                'description', COALESCE(a.description, ''),
                                'initial', COALESCE(NULLIF(a.initial, ''), LEFT(a.name, 1)),
                                'image', a.image_url,
                                'voice', a.voice_label,
                                'voice_url', a.voice_url,
                                'speaker_id', a.speaker_id,
                                'voice_status', a.voice_status,
                                'updated_at', a.updated_at,
                                'references', COALESCE((
                                    SELECT jsonb_agg(
                                        jsonb_build_object(
                                            'id', ar.id,
                                            'type', ar.type,
                                            'name', ar.name,
                                            'url', ar.url,
                                            'note', ar.note
                                        )
                                        ORDER BY ar.sort_order
                                    )
                                    FROM asset_references ar
                                    WHERE ar.asset_id = a.id
                                ), '[]'::jsonb),
                                'ref_count', (
                                    SELECT count(*)
                                    FROM asset_references ar
                                    WHERE ar.asset_id = a.id
                                )
                            )
                            ORDER BY a.updated_at DESC
                        )
                        FROM assets a
                        JOIN first_project fp ON fp.id = a.project_id
                    ), '[]'::jsonb) AS assets,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', s.id,
                                'episode_id', s.episode_id,
                                'no', s.no,
                                'title', s.title,
                                'visual', COALESCE(s.visual, ''),
                                'dialogue', COALESCE(s.dialogue, ''),
                                'characters', s.characters,
                                'scene', COALESCE(s.scene, ''),
                                'duration', s.duration,
                                'status', s.status,
                                'updated_at', s.updated_at
                            )
                            ORDER BY s.no
                        )
                        FROM shots s
                        JOIN first_episode fe ON fe.id = s.episode_id
                    ), '[]'::jsonb) AS shots,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', t.id,
                                'episode_id', t.episode_id,
                                'shot_id', t.shot_id,
                                'ai_job_id', t.ai_job_id,
                                'title', t.title,
                                'duration', t.duration,
                                'progress', t.progress,
                                'status', t.status,
                                'provider', t.provider,
                                'provider_task_id', t.provider_task_id,
                                'preview_url', t.preview_url,
                                'video_url', t.video_url,
                                'error', t.error,
                                'updated_at', t.updated_at
                            )
                            ORDER BY t.updated_at DESC
                        )
                        FROM video_tasks t
                        JOIN first_episode fe ON fe.id = t.episode_id
                    ), '[]'::jsonb) AS video_tasks,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', v.id,
                                'project_id', v.project_id,
                                'episode_id', v.episode_id,
                                'name', v.name,
                                'description', COALESCE(v.description, ''),
                                'duration', v.duration,
                                'ratio', v.ratio,
                                'status', v.status,
                                'theme', v.theme,
                                'preview_url', v.preview_url,
                                'video_url', v.video_url,
                                'created_at', v.created_at
                            )
                            ORDER BY v.created_at DESC
                        )
                        FROM video_versions v
                        JOIN first_project fp ON fp.id = v.project_id
                        WHERE NOT EXISTS (SELECT 1 FROM first_episode)
                           OR v.episode_id = (SELECT id FROM first_episode)
                    ), '[]'::jsonb) AS versions,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', l.id,
                                'user_id', l.user_id,
                                'username', CAST(:username AS text),
                                'display_name', CAST(:display_name AS text),
                                'amount', l.amount,
                                'type', l.type,
                                'scene', l.scene,
                                'description', COALESCE(l.description, ''),
                                'balance_after', l.balance_after,
                                'ai_job_id', l.ai_job_id,
                                'created_at', l.created_at
                            )
                            ORDER BY l.created_at DESC
                        )
                        FROM (
                            SELECT *
                            FROM point_ledger
                            WHERE user_id = :user_id
                            ORDER BY created_at DESC
                            LIMIT 10
                        ) l
                    ), '[]'::jsonb) AS ledger,
                    (SELECT count(*) FROM user_projects) AS project_count,
                    (SELECT count(*) FROM episodes e JOIN user_projects p ON p.id = e.project_id) AS episode_count,
                    (SELECT count(*) FROM assets a JOIN user_projects p ON p.id = a.project_id) AS asset_count,
                    (SELECT count(*) FROM video_versions v JOIN user_projects p ON p.id = v.project_id) AS version_count,
                    (SELECT count(*) FROM point_ledger WHERE user_id = :user_id) AS ledger_total,
                    (SELECT count(*) FROM users WHERE status = 'active') AS team_members
                """
            ),
            {
                "user_id": user["id"],
                "username": user.get("username", ""),
                "display_name": user.get("display_name", ""),
            },
        ).mappings().one()

        projects = list(row["projects"] or [])
        project_episodes = list(row["episodes"] or [])
        project_assets = list(row["assets"] or [])
        episode_shots = list(row["shots"] or [])
        episode_tasks = list(row["video_tasks"] or [])
        project_versions = list(row["versions"] or [])
        ledger = list(row["ledger"] or [])

        for project in projects:
            project["status_label"] = STATUS_LABEL.get(project.get("status"), project.get("status"))
        for episode in project_episodes:
            episode["status_label"] = STATUS_LABEL.get(episode.get("status"), episode.get("status"))
        usage["team_members"] = int(row["team_members"] or 0)
        current_project = projects[0] if projects else None
        selected_episode = project_episodes[0] if project_episodes else None

        return {
            "dashboard": {
                "project_count": int(row["project_count"] or 0),
                "episode_count": int(row["episode_count"] or 0),
                "version_count": int(row["version_count"] or 0),
                "asset_count": int(row["asset_count"] or 0),
                "usage": usage,
                "current_user": user,
            },
            "point_ledger": {"items": ledger, "total": int(row["ledger_total"] or 0)},
            "projects": projects,
            "current_project": current_project,
            "episodes": project_episodes,
            "selected_episode": selected_episode,
            "shots": episode_shots,
            "assets": project_assets,
            "video_tasks": episode_tasks,
            "versions": project_versions,
        }


@require_db
def episode_workspace(user: dict[str, Any], episode_id: str) -> dict[str, Any] | None:

    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                WITH target_episode AS (
                    SELECT e.id, e.project_id
                    FROM episodes e
                    JOIN projects p ON p.id = e.project_id
                    WHERE e.id = :episode_id
                      AND p.owner_user_id = :user_id
                    LIMIT 1
                )
                SELECT
                    (SELECT count(*) FROM target_episode) AS found,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', s.id,
                                'episode_id', s.episode_id,
                                'no', s.no,
                                'title', s.title,
                                'visual', COALESCE(s.visual, ''),
                                'dialogue', COALESCE(s.dialogue, ''),
                                'characters', s.characters,
                                'scene', COALESCE(s.scene, ''),
                                'duration', s.duration,
                                'status', s.status,
                                'updated_at', s.updated_at
                            )
                            ORDER BY s.no
                        )
                        FROM shots s
                        JOIN target_episode e ON e.id = s.episode_id
                    ), '[]'::jsonb) AS shots,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', t.id,
                                'episode_id', t.episode_id,
                                'shot_id', t.shot_id,
                                'ai_job_id', t.ai_job_id,
                                'title', t.title,
                                'duration', t.duration,
                                'progress', t.progress,
                                'status', t.status,
                                'provider', t.provider,
                                'provider_task_id', t.provider_task_id,
                                'preview_url', t.preview_url,
                                'video_url', t.video_url,
                                'error', t.error,
                                'updated_at', t.updated_at
                            )
                            ORDER BY t.updated_at DESC
                        )
                        FROM video_tasks t
                        JOIN target_episode e ON e.id = t.episode_id
                    ), '[]'::jsonb) AS video_tasks,
                    COALESCE((
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'id', v.id,
                                'project_id', v.project_id,
                                'episode_id', v.episode_id,
                                'name', v.name,
                                'description', COALESCE(v.description, ''),
                                'duration', v.duration,
                                'ratio', v.ratio,
                                'status', v.status,
                                'theme', v.theme,
                                'preview_url', v.preview_url,
                                'video_url', v.video_url,
                                'created_at', v.created_at
                            )
                            ORDER BY v.created_at DESC
                        )
                        FROM video_versions v
                        JOIN target_episode e ON e.project_id = v.project_id
                        WHERE v.episode_id = e.id
                    ), '[]'::jsonb) AS versions
                """
            ),
            {"episode_id": episode_id, "user_id": user["id"]},
        ).mappings().one()
        if int(row["found"] or 0) == 0:
            return None
        return {
            "shots": list(row["shots"] or []),
            "video_tasks": list(row["video_tasks"] or []),
            "versions": list(row["versions"] or []),
        }


@require_db
def dashboard(user: dict[str, Any]) -> dict[str, Any]:

    with SessionLocal() as db:
        usage = apply_usage_defaults({**(user.get("usage") or {})})
        row = db.execute(
            text(
                """
                WITH user_projects AS (
                    SELECT id
                    FROM projects
                    WHERE owner_user_id = :user_id
                )
                SELECT
                    (SELECT count(*) FROM user_projects) AS project_count,
                    (SELECT count(*) FROM episodes e JOIN user_projects p ON p.id = e.project_id) AS episode_count,
                    (SELECT count(*) FROM assets a JOIN user_projects p ON p.id = a.project_id) AS asset_count,
                    (SELECT count(*) FROM video_versions v JOIN user_projects p ON p.id = v.project_id) AS version_count,
                    (SELECT count(*) FROM users WHERE status = 'active') AS team_members
                """
            ),
            {"user_id": user["id"]},
        ).mappings().one()
        usage["team_members"] = int(row["team_members"] or 0)
        return {
            "project_count": int(row["project_count"] or 0),
            "episode_count": int(row["episode_count"] or 0),
            "version_count": int(row["version_count"] or 0),
            "asset_count": int(row["asset_count"] or 0),
            "usage": usage,
            "current_user": user,
        }
