"""
Seed the database with curated leagues from SStats.net.

Usage:
  python -m app.seed          # seed current season
  python -m app.seed 2024     # seed specific season year
"""
import logging
import sys
from app.database import engine, SessionLocal, Base
from app.services.sync import full_sync
from app.services.sstats import fetch_leagues_sync
from app.config.leagues import resolve_curated_leagues, CURATED_LEAGUES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed")

def run_seed(year: int | None = None):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        api_leagues = fetch_leagues_sync()
        if not api_leagues:
            logger.error("Seed failed — /Leagues returned empty response.")
            return

        resolved, missing = resolve_curated_leagues(api_leagues)
        if missing:
            expected = ", ".join(l.key for l in CURATED_LEAGUES)
            logger.error(
                "Seed failed — unresolved curated leagues: %s (expected keys: %s)",
                ", ".join(missing),
                expected,
            )
            return

        success = 0
        for curated, api_league in resolved:
            sstats_id = int(api_league["id"])
            logger.info("Seeding %s (sstats_id=%d)...", curated.name_ru, sstats_id)
            ok = full_sync(
                db,
                sstats_league_id=sstats_id,
                year=year,
                league_name_ru=curated.name_ru,
                league_key=curated.key,
            )
            if ok:
                success += 1
            else:
                logger.error("Failed to sync %s (sstats_id=%d)", curated.name_ru, sstats_id)

        logger.info("Seed completed: %d/%d leagues synced.", success, len(resolved))
    finally:
        db.close()


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_seed(year)
