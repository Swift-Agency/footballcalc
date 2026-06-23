import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_secret
from app.services import admin_ops
from app.services.crypto_secrets import crypto_configured

logger = logging.getLogger("admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/keys")
def get_keys(_: None = Depends(verify_admin_secret)):
    return admin_ops.keys_view()


class KeyUpdateBody(BaseModel):
    sstats_api_key: Optional[str] = None


@router.put("/keys")
def put_keys(
    payload: KeyUpdateBody,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    if not crypto_configured():
        raise HTTPException(
            status_code=400,
            detail="CRYPTO_KEY not set — cannot store keys in DB. Set CRYPTO_KEY or use env vars only.",
        )
    tg = request.headers.get("X-Telegram-User-Id")
    tg_id = int(tg) if tg and tg.isdigit() else None
    try:
        admin_ops.put_keys_op(db, payload.sstats_api_key, tg_id)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True}


@router.post("/keys/validate")
def validate_keys(db: Session = Depends(get_db), _: None = Depends(verify_admin_secret)):
    return admin_ops.validate_keys_op(db)


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db), _: None = Depends(verify_admin_secret)):
    return admin_ops.metrics_view(db)


@router.get("/cache/stats")
def cache_stats(_: None = Depends(verify_admin_secret)):
    from app.services import sstats_cache

    return sstats_cache.stats()


@router.post("/cache/clear")
def cache_clear(
    scope: str | None = Query(None),
    _: None = Depends(verify_admin_secret),
    db: Session = Depends(get_db),
):
    return admin_ops.cache_clear_op(db, scope)


class SettingsBody(BaseModel):
    cache_ttl_seconds: Optional[int] = Field(None, ge=30, le=86400)
    sstats_cache_enabled: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=0, le=10000)
    notifications_enabled: Optional[bool] = None
    feature_flags_json: Optional[str] = None


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _: None = Depends(verify_admin_secret)):
    row = admin_ops.ensure_app_settings(db)
    return {
        "cache_ttl_seconds": row.cache_ttl_seconds,
        "sstats_cache_enabled": row.sstats_cache_enabled,
        "rate_limit_per_minute": row.rate_limit_per_minute,
        "notifications_enabled": row.notifications_enabled,
        "feature_flags_json": row.feature_flags_json,
    }


@router.put("/settings")
def put_settings(
    body: SettingsBody,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    tg = request.headers.get("X-Telegram-User-Id")
    tg_id = int(tg) if tg and tg.isdigit() else None
    admin_ops.put_settings_op(
        db,
        tg_id,
        cache_ttl_seconds=body.cache_ttl_seconds,
        sstats_cache_enabled=body.sstats_cache_enabled,
        rate_limit_per_minute=body.rate_limit_per_minute,
        notifications_enabled=body.notifications_enabled,
        feature_flags_json=body.feature_flags_json,
    )
    return {"ok": True}


@router.post("/sync")
def admin_sync(
    request: Request,
    background_stats: bool = True,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    tg = request.headers.get("X-Telegram-User-Id")
    tg_id = int(tg) if tg and tg.isdigit() else None
    return admin_ops.run_sync_op(db, tg_id, background_stats)


@router.post("/seed")
def admin_seed(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    tg = request.headers.get("X-Telegram-User-Id")
    tg_id = int(tg) if tg and tg.isdigit() else None
    try:
        return admin_ops.run_seed_op(db, tg_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
