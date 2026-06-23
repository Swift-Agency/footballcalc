"""Background data sync for live football data."""
import logging
import os
import threading
import time

from app.database import SessionLocal
from app.models import League
from app.services.sync import (
    recompute_team_market_aggregates,
    sync_matches,
    sync_missing_stats,
    sync_standings,
    sync_upcoming_matches,
)

logger = logging.getLogger("data_sync_scheduler")

_started = False
_lock = threading.Lock()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _league_keys() -> list[str]:
    raw = os.getenv("DATA_SYNC_LEAGUE_KEYS", "world_cup")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _sync_once() -> None:
    keys = _league_keys()
    if not keys:
        logger.info("Data sync skipped: no league keys configured")
        return

    db = SessionLocal()
    try:
        leagues = (
            db.query(League)
            .filter(League.key.in_(keys))
            .order_by(League.id.asc())
            .all()
        )
        if not leagues:
            logger.info("Data sync skipped: no configured leagues found (keys=%s)", keys)
            return

        for league in leagues:
            try:
                logger.info("Data sync starting: league_id=%d key=%s", league.id, league.key)
                new_matches = sync_matches(db, league.id, fetch_stats=False)
                upcoming_matches = sync_upcoming_matches(db, league.id, days=7)
                standings_rows = sync_standings(db, league.id)
                filled_stats = sync_missing_stats(db, league.id)
                aggregate_rows = recompute_team_market_aggregates(db, league.id)
                db.commit()
                logger.info(
                    "Data sync complete: league_id=%d new=%d upcoming=%d standings=%d stats=%d aggregates=%d",
                    league.id,
                    new_matches,
                    upcoming_matches,
                    standings_rows,
                    filled_stats,
                    aggregate_rows,
                )
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "Data sync failed for league_id=%d key=%s: %s",
                    league.id,
                    league.key,
                    exc,
                    exc_info=True,
                )
    finally:
        db.close()


def _loop(interval_seconds: int, initial_delay_seconds: int) -> None:
    if initial_delay_seconds > 0:
        time.sleep(initial_delay_seconds)
    while True:
        started_at = time.monotonic()
        try:
            _sync_once()
        except Exception as exc:
            logger.warning("Data sync scheduler iteration failed: %s", exc, exc_info=True)

        elapsed = time.monotonic() - started_at
        time.sleep(max(5, interval_seconds - int(elapsed)))


def start_data_sync_scheduler() -> None:
    """Start live data sync loop once per process."""
    global _started
    if not _env_bool("DATA_SYNC_ENABLED", True):
        logger.info("Data sync scheduler disabled")
        return

    interval_seconds = int(os.getenv("DATA_SYNC_INTERVAL_SECONDS", "900"))
    if interval_seconds <= 0:
        logger.info("Data sync scheduler disabled by interval=%d", interval_seconds)
        return

    initial_delay_seconds = int(os.getenv("DATA_SYNC_INITIAL_DELAY_SECONDS", "30"))
    with _lock:
        if _started:
            return
        _started = True
        thread = threading.Thread(
            target=_loop,
            args=(interval_seconds, initial_delay_seconds),
            daemon=True,
            name="data-sync-scheduler",
        )
        thread.start()
    logger.info(
        "Data sync scheduler started (interval=%ds, initial_delay=%ds, keys=%s)",
        interval_seconds,
        initial_delay_seconds,
        _league_keys(),
    )
