"""Unified search across leagues, teams, and matches (ilike)."""
import logging
from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import League, Match, Team
from app.services.logo_proxy import team_logo_proxy_url

logger = logging.getLogger("search")

router = APIRouter()


@router.get("/search")
def global_search(
    q: str = Query("", max_length=200),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
) -> dict[str, List[dict[str, Any]]]:
    term = q.strip()
    if len(term) < 2:
        return {"leagues": [], "teams": [], "matches": []}

    like = f"%{term}%"

    league_rows = (
        db.query(League)
        .filter(League.name.ilike(like) | League.name_en.ilike(like))
        .order_by(League.name.asc())
        .limit(limit)
        .all()
    )
    leagues_out = [{"id": lg.id, "name": lg.name, "name_en": lg.name_en} for lg in league_rows]

    team_rows = (
        db.query(Team)
        .filter(Team.name.ilike(like) | Team.name_en.ilike(like))
        .order_by(Team.name.asc())
        .limit(limit)
        .all()
    )
    teams_out = [
        {
            "id": t.id,
            "name": t.name,
            "name_en": t.name_en,
            "league_id": t.league_id,
            "logo_url": team_logo_proxy_url(t.id, t.logo_url),
        }
        for t in team_rows
    ]

    matching_team_ids = [
        r[0]
        for r in db.query(Team.id)
        .filter(Team.name.ilike(like) | Team.name_en.ilike(like))
        .limit(limit * 3)
        .all()
    ]
    match_rows = []
    if matching_team_ids:
        match_rows = (
            db.query(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .filter(
                or_(
                    Match.home_team_id.in_(matching_team_ids),
                    Match.away_team_id.in_(matching_team_ids),
                )
            )
            .order_by(Match.date.desc())
            .limit(limit)
            .all()
        )
    matches_out = []
    for m in match_rows:
        h = m.home_team
        a = m.away_team
        matches_out.append(
            {
                "id": m.id,
                "league_id": m.league_id,
                "home_team": {"id": h.id, "name": h.name} if h else {},
                "away_team": {"id": a.id, "name": a.name} if a else {},
                "date": m.date.isoformat() if m.date else None,
                "status": m.status,
            }
        )

    logger.info(
        "GET /search q=%r → leagues=%d teams=%d matches=%d",
        term[:80],
        len(leagues_out),
        len(teams_out),
        len(matches_out),
    )
    return {"leagues": leagues_out, "teams": teams_out, "matches": matches_out}
