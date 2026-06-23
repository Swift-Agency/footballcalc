"""Cached read of AppSettings row for hot paths (SStats cache, rate limit)."""
import json
import time
from typing import Any

from app.database import SessionLocal
from app.models import AppSettings

_cached: dict = {
    "ts": 0.0,
    "ttl": 300,
    "enabled": True,
    "rate_limit": 0,
    "flags": {},
    "notifications": True,
}
_REFRESH = 15.0


def _load_row() -> None:
    db = SessionLocal()
    try:
        row = db.query(AppSettings).filter(AppSettings.id == 1).first()
        if row:
            _cached["ttl"] = row.cache_ttl_seconds
            _cached["enabled"] = row.sstats_cache_enabled
            _cached["rate_limit"] = row.rate_limit_per_minute
            _cached["notifications"] = row.notifications_enabled
            try:
                _cached["flags"] = json.loads(row.feature_flags_json or "{}")
            except json.JSONDecodeError:
                _cached["flags"] = {}
        else:
            _cached["ttl"] = 300
            _cached["enabled"] = True
            _cached["rate_limit"] = 0
            _cached["flags"] = {}
            _cached["notifications"] = True
    finally:
        db.close()


def get_cache_options() -> tuple[int, bool]:
    now = time.time()
    if now - _cached["ts"] < _REFRESH:
        return _cached["ttl"], _cached["enabled"]
    _load_row()
    _cached["ts"] = now
    return _cached["ttl"], _cached["enabled"]


def get_rate_limit_per_minute() -> int:
    now = time.time()
    if now - _cached["ts"] < _REFRESH:
        return _cached["rate_limit"]
    _load_row()
    _cached["ts"] = now
    return _cached["rate_limit"]


def get_feature_flags() -> dict[str, Any]:
    now = time.time()
    if now - _cached["ts"] < _REFRESH:
        return _cached["flags"]
    _load_row()
    _cached["ts"] = now
    return _cached["flags"]


def notifications_enabled() -> bool:
    now = time.time()
    if now - _cached["ts"] < _REFRESH:
        return _cached["notifications"]
    _load_row()
    _cached["ts"] = now
    return _cached["notifications"]


def invalidate_settings_cache() -> None:
    _cached["ts"] = 0.0
