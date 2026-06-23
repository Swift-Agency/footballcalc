"""Moscow timezone helpers for referral discount windows and API timestamps."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
REFERRAL_DISCOUNT_HOURS = 24


def moscow_now() -> datetime:
    return datetime.now(MOSCOW_TZ)


def utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def naive_utc_to_moscow(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)


def referral_discount_expires_at(from_moment: datetime | None = None) -> datetime:
    """Return UTC-naive expiry anchored to Moscow time (+24 hours)."""
    start = moscow_now() if from_moment is None else naive_utc_to_moscow(from_moment)
    return utc_naive(start + timedelta(hours=REFERRAL_DISCOUNT_HOURS))


def referral_discount_active(expires_at_utc_naive: datetime | None) -> bool:
    if not expires_at_utc_naive:
        return False
    return datetime.utcnow() < expires_at_utc_naive


def referral_claim_window_open(created_at_utc_naive: datetime) -> bool:
    start = naive_utc_to_moscow(created_at_utc_naive)
    return moscow_now() < start + timedelta(hours=REFERRAL_DISCOUNT_HOURS)


def format_utc_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
