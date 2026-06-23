"""Full league sync from SStats (used by admin API)."""
import logging
import threading

from app.database import SessionLocal
from app.models import League
from app.services.sync import (
    sync_matches,
    sync_standings,
    sync_missing_stats,
    recompute_team_market_aggregates,
    sync_upcoming_matches,
)

logger = logging.getLogger("sync_trigger")


def run_full_sync(background_stats: bool = True) -> dict:
    db = SessionLocal()
    try:
        leagues = db.query(League).order_by(League.id.asc()).all()
        if not leagues:
            return {"error": "No league in DB. Run seed first."}
        per_league = []
        total_new = 0
        total_upcoming = 0
        total_standings = 0
        total_aggregates = 0
        league_ids = [l.id for l in leagues]

        for league_id in league_ids:
            lg = db.query(League).filter(League.id == league_id).first()
            if not lg:
                continue
            new_matches = sync_matches(db, league_id, fetch_stats=False)
            upcoming_matches = sync_upcoming_matches(db, league_id, days=7)
            standings_rows = sync_standings(db, league_id)
            aggregates_rows = recompute_team_market_aggregates(db, league_id)
            db.commit()
            total_new += new_matches
            total_upcoming += upcoming_matches
            total_standings += standings_rows
            total_aggregates += aggregates_rows
            per_league.append(
                {
                    "league_id": league_id,
                    "name": lg.name,
                    "new_matches": new_matches,
                    "upcoming_matches": upcoming_matches,
                    "standings_rows": standings_rows,
                    "aggregates_rows": aggregates_rows,
                }
            )

        out = {
            "ok": True,
            "leagues": per_league,
            "totals": {
                "new_matches": total_new,
                "upcoming_matches": total_upcoming,
                "standings_rows": total_standings,
                "aggregates_rows": total_aggregates,
            },
        }

        def fill_stats():
            d = SessionLocal()
            try:
                filled_total = 0
                for lid in league_ids:
                    filled = sync_missing_stats(d, lid)
                    filled_total += filled
                    if filled:
                        recompute_team_market_aggregates(d, lid)
                        d.commit()
                logger.info("Background stats fill done: %d matches", filled_total)
            except Exception as e:
                logger.warning("Background stats fill failed: %s", e, exc_info=True)
            finally:
                d.close()

        if background_stats:
            threading.Thread(target=fill_stats, daemon=True).start()
            out["stats_fill"] = "started"
        return out
    finally:
        db.close()
