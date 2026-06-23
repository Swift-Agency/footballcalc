"""
Resolve API keys: env first, then optional DB override (RuntimeSecret) when CRYPTO_KEY is set.
"""
import os
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import RuntimeSecret

_cache: dict[str, tuple[float, str]] = {}
_TTL = 60.0

ENV_SSTATS = "SSTATS_API_KEY"
DB_SSTATS = "sstats_api_key"


def invalidate_key_cache() -> None:
    _cache.clear()


def _from_db(db: Session, name: str) -> Optional[str]:
    try:
        row = db.query(RuntimeSecret).filter(RuntimeSecret.name == name).first()
    except Exception:
        return None
    if not row:
        return None
    from app.services.crypto_secrets import decrypt_value

    return decrypt_value(row.value_encrypted)


def _get_key(db_name: str, env_name: str) -> str:
    now = time.time()
    cache_key = db_name
    if cache_key in _cache and now - _cache[cache_key][0] < _TTL:
        return _cache[cache_key][1]

    env = os.getenv(env_name, "").strip()
    out = env
    db = SessionLocal()
    try:
        override = _from_db(db, db_name)
        if override is not None:
            out = override
    finally:
        db.close()

    _cache[cache_key] = (now, out)
    return out


def get_sstats_api_key() -> str:
    return _get_key(DB_SSTATS, ENV_SSTATS)
