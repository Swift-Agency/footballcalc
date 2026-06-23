"""
TTL cache for SStats GET responses with hit/miss stats.
"""
import json
import threading
import time
from typing import Any, Optional

from cachetools import TTLCache

_lock = threading.Lock()
_hits = 0
_misses = 0

# scope -> TTLCache (max entries, ttl)
_caches: dict[str, TTLCache] = {}
_scope_ttl: dict[str, int] = {}


def _get_cache(scope: str, ttl: int, maxsize: int = 512) -> TTLCache:
    if scope not in _caches or _scope_ttl.get(scope) != ttl:
        _caches[scope] = TTLCache(maxsize=maxsize, ttl=ttl)
        _scope_ttl[scope] = ttl
    return _caches[scope]


def cache_key(path: str, params: dict) -> str:
    items = sorted((k, v) for k, v in params.items() if v is not None)
    return f"{path}?{json.dumps(items, sort_keys=True)}"


def get_cached(scope: str, key: str, ttl: int) -> Optional[Any]:
    global _hits, _misses
    with _lock:
        c = _get_cache(scope, ttl)
        if key in c:
            _hits += 1
            return c[key]
        _misses += 1
        return None


def set_cached(scope: str, key: str, ttl: int, value: Any) -> None:
    c = _get_cache(scope, ttl)
    with _lock:
        c[key] = value


def clear_scope(scope: str) -> int:
    """Return number of entries evicted."""
    with _lock:
        if scope not in _caches:
            return 0
        n = len(_caches[scope])
        _caches[scope].clear()
        return n


def clear_all() -> dict[str, int]:
    out = {}
    with _lock:
        for k, c in list(_caches.items()):
            out[k] = len(c)
            c.clear()
    return out


def stats() -> dict:
    with _lock:
        total = _hits + _misses
        hit_rate = (_hits / total * 100.0) if total else 0.0
        sizes = {scope: len(c) for scope, c in _caches.items()}
        return {
            "hits": _hits,
            "misses": _misses,
            "hit_rate_pct": round(hit_rate, 2),
            "scopes": sizes,
        }
