"""
Aggregates for admin monitoring from AppEvent + external_metrics.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import AppEvent, TelegramUserPing
from app.services import external_metrics

WindowMode = Literal["7d", "all"]

DEFAULT_TOP_N = 15
DEFAULT_SORT_TOP = 12


def _since(mode: WindowMode) -> datetime | None:
    if mode == "all":
        return None
    return datetime.now(timezone.utc) - timedelta(days=7)


def _parse_payload(row: AppEvent) -> dict[str, Any]:
    if not row.payload_json:
        return {}
    try:
        return json.loads(row.payload_json)
    except json.JSONDecodeError:
        return {}


def _events_query(db: Session, event_type: str, mode: WindowMode):
    q = db.query(AppEvent).filter(AppEvent.event_type == event_type)
    since = _since(mode)
    if since is not None:
        q = q.filter(AppEvent.created_at >= since)
    return q


def aggregate_page_views(db: Session, mode: WindowMode, top_n: int = DEFAULT_TOP_N) -> list[tuple[str, int]]:
    rows = _events_query(db, "page_view", mode).all()
    c: Counter[str] = Counter()
    for r in rows:
        path = _parse_payload(r).get("path")
        if isinstance(path, str) and path:
            c[path] += 1
        else:
            c["(без path)"] += 1
    return c.most_common(top_n)


def aggregate_searches(db: Session, mode: WindowMode, top_n: int = DEFAULT_TOP_N) -> list[tuple[str, int]]:
    rows = _events_query(db, "search", mode).all()
    c: Counter[str] = Counter()
    for r in rows:
        q = _parse_payload(r).get("query")
        if isinstance(q, str) and q.strip():
            c[q.strip()[:200]] += 1
        else:
            c["(пусто)"] += 1
    return c.most_common(top_n)


def aggregate_sort_changes(
    db: Session, mode: WindowMode, top_n: int = DEFAULT_SORT_TOP
) -> list[tuple[str, int]]:
    rows = _events_query(db, "sort_change", mode).all()
    c: Counter[str] = Counter()
    for r in rows:
        p = _parse_payload(r)
        key = p.get("key")
        direction = p.get("direction")
        if isinstance(key, str) and isinstance(direction, str):
            label = f"{key} · {direction}"
        elif isinstance(key, str):
            label = key
        else:
            label = "(неизв.)"
        c[label] += 1
    return c.most_common(top_n)


def telegram_users_count(db: Session) -> int:
    return db.query(TelegramUserPing).count()


def monitoring_snapshot(db: Session, mode: WindowMode = "7d") -> dict[str, Any]:
    """Structured data for admin UI (bot HTML formatter)."""
    ext = external_metrics.snapshot()
    return {
        "window": mode,
        "external": ext,
        "telegram_users": telegram_users_count(db),
        "page_views_top": aggregate_page_views(db, mode),
        "searches_top": aggregate_searches(db, mode),
        "sort_top": aggregate_sort_changes(db, mode),
    }
