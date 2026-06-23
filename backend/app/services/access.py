"""
Premium feature access gating.

New model (replaces league-level gating):
  - All leagues are free — standings, matches, advanced-stats, smallmarkets are all open.
  - xG tables and calculator odds are "premium features".
  - Users without an active subscription get a weekly quota of 5 uses total (xG + calculator).
  - Active subscription (monthly or world_cup plan) → unlimited.

Public API:
  get_or_create_user(init_data, db)   — parse initData, create User row if needed (referral only on signup via start_param).
  get_user_from_init_data(init_data, db) — parse only, no create (for free endpoints).
  has_active_subscription(user)       — True if subscription is active and not expired.
  get_weekly_quota(db, user)          — returns dict with used/remaining/resets_at.
  consume_premium_usage(db, user, feature) — decrement quota or raise 402.
  can_access_league(...)              — always True (kept for backward compat).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AppSettings, League, PremiumUsageEvent, Subscription, User, WEEKLY_FREE_QUOTA, WORLD_CUP_ENDS_AT
from app.services.moscow_time import (
    referral_discount_active,
    referral_discount_expires_at,
)

logger = logging.getLogger("access")

PREMIUM_FEATURES = {"xg", "calculator"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_settings(db: Session) -> AppSettings:
    return db.query(AppSettings).filter(AppSettings.id == 1).first()


def _week_start(now: Optional[datetime] = None) -> datetime:
    """Return the UTC Monday 00:00:00 of the current week."""
    if now is None:
        now = datetime.utcnow()
    return now - timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute,
                           seconds=now.second, microseconds=now.microsecond)


def _weekly_quota_limit(db: Session) -> int:
    settings = _get_settings(db)
    if settings and settings.weekly_free_quota:
        return int(settings.weekly_free_quota)
    return WEEKLY_FREE_QUOTA


# ─── Subscription check ───────────────────────────────────────────────────────

def has_active_subscription(user: Optional[User]) -> bool:
    if not user:
        return False
    sub: Optional[Subscription] = user.subscription
    if not sub:
        return False
    if sub.status != "active":
        return False
    now = datetime.utcnow()
    return sub.current_period_end > now


# ─── User resolution ──────────────────────────────────────────────────────────

def _parse_init_data(init_data: Optional[str]) -> Optional[dict]:
    """Validate Telegram initData and return parsed dict, or None on failure."""
    if not init_data:
        return None
    bot_token = os.getenv("MAIN_BOT_TOKEN", "")
    if not bot_token:
        return None
    try:
        from app.services.telegram_webapp_auth import validate_init_data
        return validate_init_data(init_data, bot_token)
    except Exception as exc:
        logger.debug("initData validation failed: %s", exc)
        return None


def get_user_from_init_data(init_data: Optional[str], db: Session) -> Optional[User]:
    """Parse initData and return existing User from DB (or None). Does NOT create."""
    data = _parse_init_data(init_data)
    if not data:
        return None
    try:
        from app.services.telegram_webapp_auth import get_telegram_user_id_from_validated
        tg_id = get_telegram_user_id_from_validated(data)
        if not tg_id:
            return None
        return db.query(User).filter(User.telegram_id == tg_id).first()
    except Exception as exc:
        logger.debug("get_user_from_init_data error: %s", exc)
        return None


def _referral_code_from_init_data(data: dict) -> Optional[str]:
    code = (data.get("start_param") or "").strip()
    return code or None


def _apply_referral_on_signup(db: Session, user: User, referral_code: str) -> None:
    """Attach inviter only for brand-new users (called once at signup)."""
    referrer = db.query(User).filter(User.referral_code == referral_code).first()
    if not referrer or referrer.id == user.id:
        return
    user.referred_by_user_id = referrer.id
    user.discount_expires_at = referral_discount_expires_at(user.created_at)
    logger.info("User %d referred by %d on signup", user.id, referrer.id)


def get_or_create_user_from_validated(
    data: dict,
    db: Session,
) -> Optional[User]:
    """Create or fetch User from validated Telegram initData payload."""
    try:
        from app.services.telegram_webapp_auth import get_telegram_user_id_from_validated
        tg_id = get_telegram_user_id_from_validated(data)
        if not tg_id:
            return None
    except Exception as exc:
        logger.debug("get_or_create_user_from_validated error: %s", exc)
        return None

    user_info = data.get("user") or {}
    user = db.query(User).filter(User.telegram_id == tg_id).first()

    if user:
        if not user.referral_code:
            import secrets
            user.referral_code = secrets.token_urlsafe(8)
            db.commit()
        return user

    import secrets
    code = secrets.token_urlsafe(8)
    user = User(
        telegram_id=tg_id,
        username=user_info.get("username"),
        first_name=user_info.get("first_name"),
        referral_code=code,
    )
    db.add(user)

    try:
        db.flush()

        referral_code = _referral_code_from_init_data(data)
        if referral_code:
            _apply_referral_on_signup(db, user, referral_code)

        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        user = db.query(User).filter(User.telegram_id == tg_id).first()
        if not user:
            raise
        if not user.referral_code:
            user.referral_code = secrets.token_urlsafe(8)
            db.commit()

    return user


def get_or_create_user(
    init_data: Optional[str],
    db: Session,
) -> Optional[User]:
    """
    Parse initData and return (or create) User.
    Referral attribution uses start_param from initData and applies only on first signup.
    """
    data = _parse_init_data(init_data)
    if not data:
        return None
    return get_or_create_user_from_validated(data, db)


# ─── League access (always open now) ─────────────────────────────────────────

def is_free_league(league: League, db: Session) -> bool:  # noqa: kept for compat
    return True


def can_access_league(league: League, user: Optional[User], db: Session) -> bool:
    return True


def check_league_access(league: League, user: Optional[User], db: Session) -> None:
    pass  # All leagues are free — no-op kept for backward compat


# ─── Weekly quota ─────────────────────────────────────────────────────────────

def get_weekly_quota(db: Session, user: Optional[User]) -> dict:
    """
    Returns quota state for the current week.
    {
        "is_unlimited": bool,
        "weekly_limit": int,
        "used": int,
        "remaining": int,
        "resets_at": ISO-8601 string (next Monday UTC),
    }
    """
    if has_active_subscription(user):
        return {
            "is_unlimited": True,
            "weekly_limit": _weekly_quota_limit(db),
            "used": 0,
            "remaining": 9999,
            "resets_at": None,
        }

    limit = _weekly_quota_limit(db)
    if not user:
        return {
            "is_unlimited": False,
            "weekly_limit": limit,
            "used": 0,
            "remaining": limit,
            "resets_at": (_week_start() + timedelta(days=7)).isoformat(),
        }

    week = _week_start()
    used = (
        db.query(PremiumUsageEvent)
        .filter(
            PremiumUsageEvent.user_id == user.id,
            PremiumUsageEvent.week_start == week,
        )
        .count()
    )
    remaining = max(0, limit - used)
    return {
        "is_unlimited": False,
        "weekly_limit": limit,
        "used": used,
        "remaining": remaining,
        "resets_at": (week + timedelta(days=7)).isoformat(),
    }


def consume_premium_usage(db: Session, user: Optional[User], feature: str) -> dict:
    """
    Attempt to consume one premium usage for `feature` ("xg" or "calculator").

    - If user has an active subscription: allow freely, return quota info.
    - If no user (not authenticated via Telegram): raise 401.
    - If quota exhausted: raise 402 with detail={"code": "quota_exhausted", ...}.
    - Otherwise: record usage, return updated quota info.
    """
    if feature not in PREMIUM_FEATURES:
        raise ValueError(f"Unknown premium feature: {feature}")

    if not user:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "auth_required",
                "message": "Откройте приложение через Telegram, чтобы использовать эту функцию.",
            },
        )

    if has_active_subscription(user):
        quota = get_weekly_quota(db, user)
        return quota

    limit = _weekly_quota_limit(db)
    week = _week_start()
    used = (
        db.query(PremiumUsageEvent)
        .filter(
            PremiumUsageEvent.user_id == user.id,
            PremiumUsageEvent.week_start == week,
        )
        .count()
    )

    if used >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "quota_exhausted",
                "message": f"Вы использовали все {limit} бесплатных запросов на этой неделе. Оформите подписку для безлимитного доступа.",
                "weekly_limit": limit,
                "used": used,
                "remaining": 0,
                "resets_at": (week + timedelta(days=7)).isoformat(),
            },
        )

    event = PremiumUsageEvent(
        user_id=user.id,
        feature=feature,
        week_start=week,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()

    remaining = max(0, limit - used - 1)
    return {
        "is_unlimited": False,
        "weekly_limit": limit,
        "used": used + 1,
        "remaining": remaining,
        "resets_at": (week + timedelta(days=7)).isoformat(),
    }


# ─── Discount eligibility ─────────────────────────────────────────────────────

def has_referral_discount(user: Optional[User]) -> bool:
    """True if the user was referred and is still within the 24h discount window (MSK)."""
    if not user:
        return False
    if not user.referred_by_user_id:
        return False
    return referral_discount_active(user.discount_expires_at)


# ─── Free league keys (kept for admin bot compat) ─────────────────────────────

def get_free_league_keys(db: Session) -> list[str]:
    env_val = os.getenv("FREE_LEAGUE_KEYS", "").strip()
    if env_val:
        return [k.strip() for k in env_val.split(",") if k.strip()]
    settings = _get_settings(db)
    if settings and settings.free_league_keys_csv:
        return [k.strip() for k in settings.free_league_keys_csv.split(",") if k.strip()]
    return ["world_cup", "ucl"]
