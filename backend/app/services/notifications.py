"""
Background alerts to admin Telegram users (ADMIN_BOT_TOKEN + ADMIN_TELEGRAM_IDS).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import NotificationDedup
from app.services import external_metrics
from app.services.settings_reader import notifications_enabled

logger = logging.getLogger("notifications")

TELEGRAM_API = "https://api.telegram.org"

_last_429_total: int | None = None
_prev_snapshot: dict[str, Any] | None = None


def _snap_metrics(snap: dict[str, Any]) -> dict[str, Any]:
    """Store comparable slices for delta alerts."""
    p = snap["sstats"]
    return {
        "sstats": {
            "errors": p["errors"],
            "http_5xx": p["http_5xx"],
            "http_429": p["http_429"],
            "last_errors": list(p.get("last_errors") or []),
        }
    }


def _can_send(db: Session, key: str, min_interval: timedelta) -> bool:
    now = datetime.now(timezone.utc)
    row = db.query(NotificationDedup).filter(NotificationDedup.key == key).first()
    if row:
        last = row.last_sent_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last) < min_interval:
            return False
    if row:
        row.last_sent_at = now
    else:
        db.add(NotificationDedup(key=key, last_sent_at=now))
    db.commit()
    return True


async def _send_message(text: str) -> None:
    token = os.getenv("ADMIN_BOT_TOKEN", "").strip()
    raw_ids = os.getenv("ADMIN_TELEGRAM_IDS", "").strip()
    if not token or not raw_ids:
        return
    ids = [x.strip() for x in raw_ids.split(",") if x.strip().isdigit()]
    if not ids:
        return
    url_base = f"{TELEGRAM_API}/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        for chat_id in ids:
            try:
                r = await client.post(url_base, json={"chat_id": int(chat_id), "text": text[:4000]})
                if not r.is_success:
                    logger.warning("sendMessage failed: %s", r.text[:200])
            except Exception as e:
                logger.warning("sendMessage error: %s", e)


async def _tick() -> None:
    global _last_429_total, _prev_snapshot
    if not notifications_enabled():
        return

    snap = external_metrics.snapshot()
    db = SessionLocal()
    try:
        if _prev_snapshot is None:
            _prev_snapshot = _snap_metrics(snap)
            s429 = snap["sstats"]["http_429"]
            if _last_429_total is None:
                _last_429_total = s429
            return

        prev = _prev_snapshot

        # HTTP 429 burst (SStats)
        s429 = snap["sstats"]["http_429"]
        if _last_429_total is None:
            _last_429_total = s429
        else:
            delta = s429 - _last_429_total
            _last_429_total = s429
            if delta >= 4 and _can_send(db, "sstats_429_burst", timedelta(hours=1)):
                await _send_message(
                    f"⚠️ SStats: за минуту зафиксировано +{delta} ответов HTTP 429 "
                    f"(всего с момента запуска: {s429}). Возможен лимит API."
                )

        name, label = "sstats", "SStats"
        de = snap[name]["errors"] - prev[name]["errors"]
        if de >= 5 and _can_send(db, f"errors_spike_{name}", timedelta(hours=1)):
            await _send_message(
                f"⚠️ {label}: +{de} сетевых/прочих ошибок за минуту "
                f"(всего с запуска: {snap[name]['errors']})."
            )
        d5 = snap[name]["http_5xx"] - prev[name]["http_5xx"]
        if d5 >= 3 and _can_send(db, f"http5xx_{name}", timedelta(hours=1)):
            await _send_message(
                f"⚠️ {label}: +{d5} ответов HTTP 5xx за минуту "
                f"(всего с запуска: {snap[name]['http_5xx']}). Сервис может быть недоступен."
            )

        cur_tail = (snap[name].get("last_errors") or [])[-1:] if snap[name].get("last_errors") else []
        old_tail = (prev[name].get("last_errors") or [])[-1:] if prev[name].get("last_errors") else []
        cur_e = cur_tail[0] if cur_tail else None
        old_e = old_tail[0] if old_tail else None
        if cur_e and cur_e != old_e and _can_send(db, f"err_tail_{name}", timedelta(minutes=30)):
            short = cur_e[:800]
            await _send_message(f"⚠️ {label}: новая ошибка в логе:\n{short}")

    finally:
        _prev_snapshot = _snap_metrics(snap)
        db.close()


async def run_notification_loop() -> None:
    while True:
        try:
            await asyncio.sleep(60)
            await _tick()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("notification tick failed: %s", e, exc_info=True)


_task: asyncio.Task | None = None


def start_notification_loop() -> None:
    global _task
    if os.getenv("ADMIN_BOT_TOKEN", "").strip() and os.getenv("ADMIN_TELEGRAM_IDS", "").strip():
        _task = asyncio.create_task(run_notification_loop())
        logger.info("Admin notification loop started")
