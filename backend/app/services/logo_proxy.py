import threading
import time
from dataclasses import dataclass
from typing import Optional

from app.services.national_flags import national_flag_url

import httpx

from app.services.sstats import SSTATS_BASE

_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE_MAX_ITEMS = 512
_REQUEST_TIMEOUT_SECONDS = 12


@dataclass
class _CachedLogo:
    content: bytes
    content_type: str
    cached_at: float


_cache: dict[str, _CachedLogo] = {}
_cache_lock = threading.Lock()


def team_logo_proxy_url(team_id: int, raw_logo_url: Optional[str]) -> Optional[str]:
    """Return same-origin URL for team logos so WebView doesn't fetch third-party domains."""
    if not raw_logo_url:
        return None
    if raw_logo_url.startswith("/api/team-logos/"):
        return raw_logo_url
    return f"/api/team-logos/{team_id}"


def resolve_team_logo_url(
    team_id: int,
    logo_url: Optional[str],
    name_en: Optional[str] = None,
) -> Optional[str]:
    """Use SStats logo when present, otherwise national-team flag fallback."""
    return team_logo_proxy_url(team_id, logo_url or national_flag_url(name_en))


def normalize_logo_source_url(raw_logo_url: Optional[str]) -> Optional[str]:
    if not raw_logo_url:
        return None
    url = str(raw_logo_url).strip()
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    if url.startswith("/"):
        return f"{SSTATS_BASE}{url}"
    return url


def fetch_logo_bytes(source_url: str) -> _CachedLogo:
    now = time.time()
    with _cache_lock:
        cached = _cache.get(source_url)
        if cached and (now - cached.cached_at) < _CACHE_TTL_SECONDS:
            return cached

    resp = httpx.get(
        source_url,
        timeout=_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": "FootballCalculator/1.0 (+logo-proxy)",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    resp.raise_for_status()
    content = resp.content
    if not content:
        raise ValueError("Empty image body")

    content_type = (resp.headers.get("Content-Type") or "image/png").split(";")[0].strip()
    if not content_type.startswith("image/"):
        content_type = "image/png"

    fresh = _CachedLogo(content=content, content_type=content_type, cached_at=now)
    with _cache_lock:
        _cache[source_url] = fresh
        if len(_cache) > _CACHE_MAX_ITEMS:
            oldest_key = min(_cache, key=lambda key: _cache[key].cached_at)
            _cache.pop(oldest_key, None)
    return fresh
