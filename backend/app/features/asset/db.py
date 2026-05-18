"""Asset database access. No HTTP exceptions here."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from ...db import AsyncSessionLocal, require_db
from ...models import AiJob, Asset, AssetReference, Project, User
from ...serializers import _asset_dict
from ...utils import parse_dt, uid
from ..points.db import change_points
from ..ai_job.db import add_ai_job


@require_db
async def list_assets(user: dict[str, Any], project_id: str, asset_type: str | None = None) -> list[dict[str, Any]] | None:

    async with AsyncSessionLocal() as db:
        owned = await db.scalar(select(Project.id).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        if not owned:
            return None
        query = select(Asset).where(Asset.project_id == project_id)
        if asset_type:
            query = query.where(Asset.type == asset_type)
        asset_rows = list(await db.scalars(query.order_by(Asset.updated_at.desc())))
        refs_by_asset: dict[str, list[dict]] = defaultdict(list)
        asset_ids = [asset.id for asset in asset_rows]
        if asset_ids:
            ref_rows = await db.scalars(
                select(AssetReference)
                .where(AssetReference.asset_id.in_(asset_ids))
                .order_by(AssetReference.sort_order)
            )
            for ref in ref_rows:
                refs_by_asset[ref.asset_id].append(
                    {
                        "id": ref.id,
                        "type": ref.type,
                        "name": ref.name,
                        "url": ref.url,
                        "note": ref.note,
                    }
                )
        return [_asset_dict(asset, refs_by_asset.get(asset.id, [])) for asset in asset_rows]


@require_db
async def get_asset(user: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as db:
        asset = await db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return None
        refs = [
            {"id": ref.id, "type": ref.type, "name": ref.name, "url": ref.url, "note": ref.note}
            for ref in await db.scalars(select(AssetReference).where(AssetReference.asset_id == asset_id).order_by(AssetReference.sort_order))
        ]
        return _asset_dict(asset, refs)


@require_db
async def _create_asset_common(
    db: Any,
    user_id: str,
    project_id: str,
    payload: Any,
    refs: list[dict],
    cost: int,
    ts: datetime,
    points_scene: str,
    points_desc: str,
    image_url: str | None,
    initial: str | None,
    voice_label: str | None,
    voice_url: str | None,
    voice_status: str | None,
) -> tuple[Asset, list[dict]] | dict[str, Any] | None:
    """Shared logic for create_asset and generate_asset."""
    project = await db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user_id))
    target_user = await db.get(User, user_id)
    if not project or not target_user:
        return None
    try:
        await change_points(db, user_id, -cost, "consume", points_scene, points_desc, ts)
    except ValueError as exc:
        return {"error": str(exc)}
    asset = Asset(
        id=uid("asset"),
        project_id=project_id,
        type=payload.type,
        name=payload.name,
        description=payload.description,
        initial=initial or payload.name[:1],
        image_url=image_url,
        voice_label=voice_label,
        voice_url=voice_url,
        voice_status=voice_status,
        provider_meta={},
        updated_at=ts,
    )
    db.add(asset)
    await db.flush()
    for index, ref in enumerate(refs):
        db.add(
            AssetReference(
                id=ref.get("id") or uid("ref"),
                asset_id=asset.id,
                type=ref.get("type", "image"),
                name=ref.get("name") or f"参考 {index + 1}",
                url=ref.get("url"),
                note=ref.get("note"),
                sort_order=index,
            )
        )
    visual_asset = payload.type in {"character", "scene", "image"}
    if visual_asset:
        usage = dict(target_user.usage_json or {})
        usage.setdefault("image_total", 1000)
        usage.setdefault("image_used", 0)
        usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)
        target_user.usage_json = usage
    project.updated_at = ts
    return asset, refs


@require_db
async def create_asset(user: dict[str, Any], project_id: str, payload: Any, refs: list[dict], cost: int, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        result = await _create_asset_common(
            db, user["id"], project_id, payload, refs, cost, ts,
            points_scene="创建素材",
            points_desc=f"创建素材《{payload.name}》",
            image_url=payload.image,
            initial=payload.initial[:1] if payload.initial else None,
            voice_label=payload.voice,
            voice_url=payload.voice_url,
            voice_status="uploaded" if payload.voice_url else None,
        )
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        asset, asset_refs = result
        await db.commit()
        return _asset_dict(asset, asset_refs)


@require_db
async def generate_asset(user: dict[str, Any], project_id: str, payload: Any, generated_url: str | None, refs: list[dict], cost: int, provider: str, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    visual_asset = payload.type in {"character", "scene", "image"}
    async with AsyncSessionLocal() as db:
        result = await _create_asset_common(
            db, user["id"], project_id, payload, refs, cost, ts,
            points_scene="AI 生成素材",
            points_desc=f"AI 生成素材《{payload.name}》",
            image_url=generated_url,
            initial=None,
            voice_label=None,
            voice_url=None,
            voice_status=None,
        )
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        asset, asset_refs = result
        await add_ai_job(db, user["id"], "image_asset" if visual_asset else "audio_asset", provider, cost, ts, project_id=project_id, asset_id=asset.id)
        await db.commit()
        return _asset_dict(asset, asset_refs)


@require_db
async def generate_asset_without_charge(user: dict[str, Any], project_id: str, payload: Any, generated_url: str | None, refs: list[dict], timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        project = await db.scalar(select(Project).where(Project.id == project_id, Project.owner_user_id == user["id"]))
        target_user = await db.get(User, user["id"])
        if not project or not target_user:
            return None
        asset = Asset(
            id=uid("asset"),
            project_id=project_id,
            type=payload.type,
            name=payload.name,
            description=payload.description,
            initial=payload.name[:1],
            image_url=generated_url,
            voice_label=None,
            voice_url=None,
            voice_status=None,
            provider_meta={},
            updated_at=ts,
        )
        db.add(asset)
        await db.flush()
        for index, ref in enumerate(refs):
            db.add(
                AssetReference(
                    id=ref.get("id") or uid("ref"),
                    asset_id=asset.id,
                    type=ref.get("type", "image"),
                    name=ref.get("name") or f"参考 {index + 1}",
                    url=ref.get("url"),
                    note=ref.get("note"),
                    sort_order=index,
                )
            )
        if payload.type in {"character", "scene", "image"}:
            usage = dict(target_user.usage_json or {})
            usage.setdefault("image_total", 1000)
            usage.setdefault("image_used", 0)
            usage["image_used"] = min(usage["image_total"], usage["image_used"] + 1)
            target_user.usage_json = usage
        project.updated_at = ts
        await db.flush()
        result = _asset_dict(asset, refs)
        await db.commit()
        return result


@require_db
async def update_asset(user: dict[str, Any], asset_id: str, payload: Any, refs: list[dict] | None, timestamp: str) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        asset = await db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return None
        updates = payload.model_dump(exclude_unset=True)
        field_map = {
            "name": "name",
            "description": "description",
            "initial": "initial",
            "image": "image_url",
            "voice": "voice_label",
            "voice_url": "voice_url",
            "voice_status": "voice_status",
            "speaker_id": "speaker_id",
        }
        for source, target in field_map.items():
            if source in updates:
                value = updates[source]
                if source == "initial" and value:
                    value = value[:1]
                setattr(asset, target, value)
        asset.updated_at = ts
        if refs is not None:
            await db.execute(delete(AssetReference).where(AssetReference.asset_id == asset_id))
            for index, ref in enumerate(refs):
                db.add(
                    AssetReference(
                        id=ref.get("id") or uid("ref"),
                        asset_id=asset_id,
                        type=ref.get("type", "image"),
                        name=ref.get("name") or f"参考 {index + 1}",
                        url=ref.get("url"),
                        note=ref.get("note"),
                        sort_order=index,
                    )
                )
        project = await db.get(Project, asset.project_id)
        if project:
            project.updated_at = ts
        await db.flush()
        ref_dicts = refs if refs is not None else [
            {"id": ref.id, "type": ref.type, "name": ref.name, "url": ref.url, "note": ref.note}
            for ref in await db.scalars(select(AssetReference).where(AssetReference.asset_id == asset_id).order_by(AssetReference.sort_order))
        ]
        result = _asset_dict(asset, ref_dicts)
        await db.commit()
        return result


@require_db
async def delete_asset(user: dict[str, Any], asset_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        asset = await db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return False
        await db.delete(asset)
        await db.commit()
        return True


@require_db
async def update_voice_clone(user: dict[str, Any], asset_id: str, result: dict[str, Any], cost: int, timestamp: str, consume: bool = True, job_id: str | None = None) -> dict[str, Any] | None:
    ts = parse_dt(timestamp)
    async with AsyncSessionLocal() as db:
        asset = await db.scalar(
            select(Asset)
            .join(Project, Project.id == Asset.project_id)
            .where(Asset.id == asset_id, Project.owner_user_id == user["id"])
        )
        if not asset:
            return None
        job = await db.get(AiJob, job_id) if job_id else None
        if consume:
            try:
                await change_points(db, user["id"], -cost, "consume", "音色克隆", f"训练《{asset.name}》角色音色", ts)
            except ValueError as exc:
                return {"error": str(exc)}
        for key, attr in {"speaker_id": "speaker_id", "voice_url": "voice_url", "voice_status": "voice_status", "error": None}.items():
            if key in result and attr:
                setattr(asset, attr, result[key])
        asset.updated_at = ts
        if job:
            job.provider_task_id = asset.speaker_id
            job.project_id = asset.project_id
            job.asset_id = asset_id
            job.status = "succeeded" if asset.voice_status == "completed" else "running"
            job.progress = 100 if asset.voice_status == "completed" else 0
            job.updated_at = ts
            if asset.voice_status == "completed":
                job.completed_at = ts
        elif consume:
            await add_ai_job(
                db,
                user["id"],
                "voice_clone",
                "volc_voice",
                cost,
                ts,
                status="succeeded" if asset.voice_status == "completed" else "running",
                progress=100 if asset.voice_status == "completed" else 0,
                provider_task_id=asset.speaker_id,
                project_id=asset.project_id,
                asset_id=asset_id,
            )
        await db.commit()
        return _asset_dict(asset)
