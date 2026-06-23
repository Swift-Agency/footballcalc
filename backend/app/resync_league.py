"""
Re-sync a single curated league without dropping the whole database.

Usage:
  python -m app.resync_league world_cup
  python -m app.resync_league world_cup 2026
"""
import logging
import sys

from sqlalchemy.orm import Session

from app.config.leagues import CURATED_LEAGUES, resolve_curated_leagues
from app.database import SessionLocal
from app.models import (
    League,
    Match,
    MatchStatistics,
    MatchXG,
    Standing,
    SyncRun,
    Team,
    TeamMarketAggregate,
)
from app.services.sstats import fetch_leagues_sync
from app.services.sync import full_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("resync_league")


def delete_league_data(db: Session, league_id: int) -> None:
    """Remove all rows tied to a league (matches, teams, standings, etc.)."""
    match_ids = [
        row[0]
        for row in db.query(Match.id).filter(Match.league_id == league_id).all()
    ]
    if match_ids:
        db.query(MatchStatistics).filter(MatchStatistics.match_id.in_(match_ids)).delete(
            synchronize_session=False
        )
        db.query(MatchXG).filter(MatchXG.match_id.in_(match_ids)).delete(
            synchronize_session=False
        )
    db.query(Match).filter(Match.league_id == league_id).delete(synchronize_session=False)
    db.query(Standing).filter(Standing.league_id == league_id).delete(synchronize_session=False)
    db.query(TeamMarketAggregate).filter(TeamMarketAggregate.league_id == league_id).delete(
        synchronize_session=False
    )
    db.query(SyncRun).filter(SyncRun.league_id == league_id).delete(synchronize_session=False)
    db.query(Team).filter(Team.league_id == league_id).delete(synchronize_session=False)
    db.query(League).filter(League.id == league_id).delete(synchronize_session=False)
    db.commit()


def resync_curated_league(db: Session, league_key: str, year: int | None = None) -> bool:
    curated = next((item for item in CURATED_LEAGUES if item.key == league_key), None)
    if not curated:
        known = ", ".join(item.key for item in CURATED_LEAGUES)
        logger.error("Unknown league key %r (known: %s)", league_key, known)
        return False

    api_leagues = fetch_leagues_sync()
    if not api_leagues:
        logger.error("Failed to fetch leagues from SStats")
        return False

    resolved, missing = resolve_curated_leagues(api_leagues)
    if league_key in missing:
        logger.error("Could not resolve %s against /Leagues", league_key)
        return False

    _, api_league = next(item for item in resolved if item[0].key == league_key)
    sstats_id = int(api_league["id"])
    logger.info(
        "Resolved %s -> sstats_id=%d name=%s",
        league_key,
        sstats_id,
        api_league.get("name"),
    )

    existing = db.query(League).filter(League.key == league_key).first()
    if existing:
        logger.info(
            "Removing existing league id=%d (%s, sstats_id=%s)",
            existing.id,
            existing.name_en,
            existing.sstats_id,
        )
        delete_league_data(db, existing.id)

    return full_sync(
        db,
        sstats_league_id=sstats_id,
        year=year,
        league_name_ru=curated.name_ru,
        league_key=curated.key,
    )


def main() -> None:
    if len(sys.argv) < 2:
        keys = ", ".join(item.key for item in CURATED_LEAGUES)
        logger.error("Usage: python -m app.resync_league <league_key> [year]")
        logger.error("Known keys: %s", keys)
        sys.exit(1)

    league_key = sys.argv[1]
    year = int(sys.argv[2]) if len(sys.argv) > 2 else None

    db = SessionLocal()
    try:
        ok = resync_curated_league(db, league_key, year=year)
    finally:
        db.close()

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
