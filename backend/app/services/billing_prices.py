"""Centralized subscription pricing from AppSettings."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AppSettings, WORLD_CUP_ENDS_AT

DEFAULT_PRICE_RUB = Decimal("480.00")
REFERRAL_DISCOUNT_PERCENT = 50


def get_or_create_settings(db: Session) -> AppSettings:
    settings = db.query(AppSettings).filter(AppSettings.id == 1).first()
    if not settings:
        settings = AppSettings(
            id=1,
            cache_ttl_seconds=300,
            sstats_cache_enabled=True,
            feature_flags_json="{}",
            rate_limit_per_minute=0,
            notifications_enabled=True,
        )
        db.add(settings)
        db.flush()
    return settings


def get_regular_price(settings: Optional[AppSettings]) -> Decimal:
    if settings and settings.subscription_price_rub is not None:
        return Decimal(str(settings.subscription_price_rub))
    return DEFAULT_PRICE_RUB


def get_discount_price(settings: Optional[AppSettings]) -> Decimal:
    regular = get_regular_price(settings)
    multiplier = Decimal(100 - REFERRAL_DISCOUNT_PERCENT) / Decimal(100)
    return (regular * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_billing_config_payload(settings: AppSettings) -> dict:
    import os
    regular = get_regular_price(settings)
    discount = get_discount_price(settings)
    weekly_quota = getattr(settings, "weekly_free_quota", None) or 5
    bot_username = os.getenv("MAIN_BOT_USERNAME", "").strip().lstrip("@")
    return {
        "price_rub": float(regular),
        "discount_price_rub": float(discount),
        "period_days": settings.subscription_period_days or 30,
        "world_cup_ends_at": WORLD_CUP_ENDS_AT.isoformat(),
        "weekly_free_quota": int(weekly_quota),
        "referral_discount_percent": REFERRAL_DISCOUNT_PERCENT,
        "bot_username": bot_username or None,
    }
