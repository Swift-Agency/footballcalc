"""
In-memory counters for external API calls (SStats).
"""
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

_lock = threading.Lock()

MAX_LAST_ERRORS = 20


@dataclass
class ProviderStats:
    total: int = 0
    success: int = 0
    http_4xx: int = 0
    http_5xx: int = 0
    http_429: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    last_errors: Deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LAST_ERRORS))


_sstats = ProviderStats()


def record_sstats(status_code: int | None, latency_ms: float, err: str | None = None) -> None:
    with _lock:
        _sstats.total += 1
        if err:
            _sstats.errors += 1
            _sstats.last_errors.append(err[:500])
        elif status_code == 200:
            _sstats.success += 1
        elif status_code == 429:
            _sstats.http_429 += 1
        elif status_code and 400 <= status_code < 500:
            _sstats.http_4xx += 1
        elif status_code and status_code >= 500:
            _sstats.http_5xx += 1
        else:
            _sstats.errors += 1
        _sstats.total_latency_ms += latency_ms


def snapshot() -> dict:
    with _lock:

        def pack(p: ProviderStats) -> dict:
            avg = (p.total_latency_ms / p.total) if p.total else 0.0
            return {
                "total": p.total,
                "success": p.success,
                "http_4xx": p.http_4xx,
                "http_5xx": p.http_5xx,
                "http_429": p.http_429,
                "errors": p.errors,
                "avg_latency_ms": round(avg, 2),
                "last_errors": list(p.last_errors),
            }

        return {
            "sstats": pack(_sstats),
            "ts": time.time(),
        }
