"""Shared admin operations (HTTP router + Telegram bot)."""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.models import AdminAuditLog, AppEvent, AppSettings, RuntimeSecret, TelegramUserPing
from app.models import DeletedUserBlock, LegalAcceptance
from app.services import admin_access, legal
from app.services import sstats_cache
from app.services.crypto_secrets import crypto_configured, encrypt_value
from app.services.effective_keys import ENV_SSTATS, invalidate_key_cache
from app.services.effective_keys import get_sstats_api_key as eff_sstats
from app.services import admin_analytics
from app.services import external_metrics
from app.services.admin_analytics import WindowMode
from app.services.settings_reader import invalidate_settings_cache
from app.services.sync_trigger import run_full_sync

logger = logging.getLogger("admin_ops")


def audit(
    db: Session,
    action: str,
    detail: str | None = None,
    telegram_user_id: int | None = None,
) -> None:
    log = AdminAuditLog(
        action=action,
        detail=detail[:2000] if detail else None,
        telegram_user_id=telegram_user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()


def ensure_app_settings(db: Session) -> AppSettings:
    r = db.query(AppSettings).filter(AppSettings.id == 1).first()
    if not r:
        r = AppSettings(id=1)
        db.add(r)
        db.commit()
        db.refresh(r)
    return r


def mask_key(k: str) -> dict:
    if not k:
        return {"set": False, "masked": None}
    tail = k[-4:] if len(k) >= 4 else k
    return {"set": True, "masked": f"****{tail}"}


def keys_view() -> dict:
    return {
        "sstats": mask_key(eff_sstats()),
        "crypto_configured": crypto_configured(),
        "env_sstats_set": bool(os.getenv(ENV_SSTATS, "").strip()),
    }


def validate_keys_op(db: Session) -> dict:
    """Ping SStats with the effective key via GET /Account/Info (same as manual curl check)."""
    sstats_base = os.getenv("SSTATS_API_URL", "https://api.sstats.net").rstrip("/")
    out: dict[str, Any] = {"sstats": {}}

    key = eff_sstats()
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                f"{sstats_base}/Account/Info",
                params={"apikey": key} if key else {},
            )
        payload: dict[str, Any] = {}
        if r.content:
            try:
                payload = r.json()
            except Exception:
                payload = {}
        data = payload.get("data") if isinstance(payload, dict) else None
        account_user = None
        if isinstance(data, dict):
            account_user = data.get("userName")
        ok = r.status_code == 200
        err_msg: str | None = None
        if not ok:
            if isinstance(payload, dict) and payload.get("message"):
                err_msg = str(payload["message"])
            elif r.text:
                err_msg = r.text[:300]
        sstats_out: dict[str, Any] = {
            "http_status": r.status_code,
            "ok": ok,
            "endpoint": "/Account/Info",
        }
        if account_user is not None:
            sstats_out["account_user"] = account_user
        if err_msg:
            sstats_out["error"] = err_msg
        out["sstats"] = sstats_out
    except Exception as e:
        out["sstats"] = {"ok": False, "error": str(e), "endpoint": "/Account/Info"}

    audit(db, "keys_validate", json.dumps(out)[:1900])
    return out


def metrics_view(db: Session) -> dict:
    snap = external_metrics.snapshot()
    cache = sstats_cache.stats()

    event_counts = {}
    try:
        from sqlalchemy import func

        rows = (
            db.query(AppEvent.event_type, func.count(AppEvent.id))
            .group_by(AppEvent.event_type)
            .all()
        )
        event_counts = {r[0]: r[1] for r in rows}
    except Exception:
        pass

    users_count = db.query(TelegramUserPing).count()

    return {
        **snap,
        "sstats_cache": cache,
        "app_events_by_type": event_counts,
        "telegram_users_tracked": users_count,
    }


def monitoring_dashboard(db: Session, mode: WindowMode = "7d") -> dict:
    """Rich monitoring for admin bot / API (AppEvent aggregates + external metrics)."""
    return admin_analytics.monitoring_snapshot(db, mode)


def toggle_leagues_section(db: Session, telegram_user_id: int | None) -> dict[str, bool]:
    row = ensure_app_settings(db)
    try:
        flags = json.loads(row.feature_flags_json or "{}")
    except json.JSONDecodeError:
        flags = {}
    cur = flags.get("leagues", True)
    if not isinstance(cur, bool):
        cur = True
    flags["leagues"] = not cur
    row.feature_flags_json = json.dumps(flags, ensure_ascii=False)
    db.commit()
    invalidate_settings_cache()
    audit(db, "feature_toggle", json.dumps({"leagues": flags["leagues"]}), telegram_user_id)
    return {"leagues": flags["leagues"]}


def toggle_notifications_enabled(db: Session, telegram_user_id: int | None) -> dict[str, bool]:
    row = ensure_app_settings(db)
    row.notifications_enabled = not row.notifications_enabled
    db.commit()
    invalidate_settings_cache()
    audit(
        db,
        "settings_update",
        f"notifications_enabled={row.notifications_enabled}",
        telegram_user_id,
    )
    return {"notifications_enabled": row.notifications_enabled}


def toggle_sstats_cache_enabled(db: Session, telegram_user_id: int | None) -> dict[str, bool]:
    row = ensure_app_settings(db)
    row.sstats_cache_enabled = not row.sstats_cache_enabled
    db.commit()
    invalidate_settings_cache()
    audit(
        db,
        "settings_update",
        f"sstats_cache_enabled={row.sstats_cache_enabled}",
        telegram_user_id,
    )
    return {"sstats_cache_enabled": row.sstats_cache_enabled}


def cache_clear_op(db: Session, scope: str | None) -> dict:
    if scope:
        n = sstats_cache.clear_scope(scope)
        audit(db, "cache_clear", f"scope={scope} entries={n}")
        return {"ok": True, "scope": scope, "evicted": n}
    sizes = sstats_cache.clear_all()
    audit(db, "cache_clear", f"all scopes {sizes}")
    return {"ok": True, "cleared": sizes}


def put_keys_op(
    db: Session,
    sstats_api_key: Optional[str],
    telegram_user_id: int | None,
) -> None:
    """Persist only SStats key in runtime_secrets; remove legacy api_football_key row if present."""
    db.query(RuntimeSecret).filter(RuntimeSecret.name == "api_football_key").delete()

    if sstats_api_key is not None:
        val = sstats_api_key.strip()
        name = "sstats_api_key"
        if not val:
            db.query(RuntimeSecret).filter(RuntimeSecret.name == name).delete()
        else:
            enc = encrypt_value(val)
            if not enc:
                raise ValueError("Encryption failed")
            row = db.query(RuntimeSecret).filter(RuntimeSecret.name == name).first()
            if row:
                row.value_encrypted = enc
            else:
                db.add(RuntimeSecret(name=name, value_encrypted=enc))
        invalidate_key_cache()

    db.commit()
    audit(db, "keys_update", "sstats key updated", telegram_user_id)


def run_sync_op(db: Session, telegram_user_id: int | None, background_stats: bool) -> dict:
    out = run_full_sync(background_stats=background_stats)
    audit(
        db,
        "sync",
        json.dumps(out)[:1900] if isinstance(out, dict) else str(out)[:1900],
        telegram_user_id,
    )
    return out


def run_seed_op(db: Session, telegram_user_id: int | None) -> dict:
    from app.seed import run_seed

    try:
        run_seed()
        audit(db, "seed", "ok", telegram_user_id)
        return {"ok": True}
    except Exception as e:
        logger.exception("seed failed")
        audit(db, "seed", f"error: {e}", telegram_user_id)
        raise


def put_settings_op(
    db: Session,
    telegram_user_id: int | None,
    cache_ttl_seconds: Optional[int] = None,
    sstats_cache_enabled: Optional[bool] = None,
    rate_limit_per_minute: Optional[int] = None,
    notifications_enabled: Optional[bool] = None,
    feature_flags_json: Optional[str] = None,
) -> None:
    row = ensure_app_settings(db)
    if cache_ttl_seconds is not None:
        row.cache_ttl_seconds = cache_ttl_seconds
    if sstats_cache_enabled is not None:
        row.sstats_cache_enabled = sstats_cache_enabled
    if rate_limit_per_minute is not None:
        row.rate_limit_per_minute = rate_limit_per_minute
    if notifications_enabled is not None:
        row.notifications_enabled = notifications_enabled
    if feature_flags_json is not None:
        json.loads(feature_flags_json)
        row.feature_flags_json = feature_flags_json
    db.commit()
    invalidate_settings_cache()
    audit(db, "settings_update", "app_settings row updated", telegram_user_id)


def legal_current(db: Session) -> dict[str, Any]:
    row = legal.get_active_legal_document(db)
    return {
        "version": row.version,
        "terms_url": row.terms_url,
        "privacy_url": row.privacy_url,
        "disclaimer_url": row.disclaimer_url,
        "effective_at_msk": row.effective_at_msk.isoformat(sep=" ") if row.effective_at_msk else None,
    }


def legal_update_active(
    db: Session,
    *,
    telegram_user_id: int,
    version: str,
    terms_url: str,
    privacy_url: str,
    disclaimer_url: str,
    effective_at_msk: datetime | None = None,
) -> dict[str, Any]:
    row = legal.upsert_active_legal_document(
        db,
        actor_tg_id=telegram_user_id,
        version=version,
        terms_url=terms_url,
        privacy_url=privacy_url,
        disclaimer_url=disclaimer_url,
        effective_at_msk=effective_at_msk,
    )
    audit(
        db,
        "legal_update",
        f"version={row.version} terms={row.terms_url} privacy={row.privacy_url} disclaimer={row.disclaimer_url}",
        telegram_user_id,
    )
    return legal_current(db)


def legal_acceptance_stats(db: Session) -> dict[str, int]:
    return legal.legal_stats(db)


def admins_list(db: Session) -> list[dict[str, Any]]:
    return [
        {
            "telegram_id": row.telegram_id,
            "is_active": row.is_active,
            "is_superadmin": row.is_superadmin,
        }
        for row in admin_access.list_admins(db)
    ]


def add_admin_op(db: Session, actor_tg_id: int, target_tg_id: int) -> dict[str, Any]:
    row = admin_access.add_admin(db, actor_tg_id, target_tg_id)
    audit(db, "admin_add", f"target={target_tg_id}", actor_tg_id)
    return {"telegram_id": row.telegram_id, "is_active": row.is_active}


def remove_admin_op(db: Session, actor_tg_id: int, target_tg_id: int) -> dict[str, Any]:
    row = admin_access.disable_admin(db, actor_tg_id, target_tg_id)
    if not row:
        return {"ok": False, "reason": "not_found"}
    audit(db, "admin_disable", f"target={target_tg_id}", actor_tg_id)
    return {
        "ok": True,
        "telegram_id": row.telegram_id,
        "is_active": row.is_active,
        "is_superadmin": row.is_superadmin,
    }


def broadcast_targets(db: Session) -> list[int]:
    accepted = {int(x[0]) for x in db.query(LegalAcceptance.telegram_id).distinct().all()}
    users = {int(x[0]) for x in db.query(TelegramUserPing.telegram_user_id).all()}
    blocked = {int(x[0]) for x in db.query(DeletedUserBlock.telegram_id).distinct().all()}
    return sorted((accepted | users) - blocked)
