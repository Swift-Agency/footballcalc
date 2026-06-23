import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import League, Standing, Team, Match
from app.schemas import (
    LeagueOut,
    StandingRow,
    StandingGroup,
    StandingsResponse,
    TeamShort,
    AdvancedStatsRow,
    SmallMarketRow,
    XgRow,
    MatchOut,
    MatchTeamStats,
    MatchDetailOut,
    CalculatorResult,
    TeamProfileResponse,
    TeamProfileSummary,
    TeamSmallmarketMetric,
    TeamProfileXg,
)
from app.services.stats import compute_advanced_stats, compute_smallmarket_stats, compute_xg_stats
from app.services.calculator import calculate_match_odds
from app.services.sync import sync_upcoming_matches
from app.services import access as access_svc
from app.config.leagues import league_display_index

logger = logging.getLogger("leagues")

router = APIRouter()

VALID_METRICS = ["yellow_cards", "corners", "shots_on_target", "shots_total", "fouls", "offsides"]


@router.get("/leagues", response_model=List[LeagueOut])
def list_leagues(
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    leagues = db.query(League).all()
    leagues.sort(key=lambda league: league_display_index(league.key))
    logger.info("GET /leagues → %d rows", len(leagues))
    result = []
    for league in leagues:
        out = LeagueOut.model_validate(league)
        out.is_locked = False  # All leagues are free — no league-level lock
        result.append(out)
    return result


@router.get("/leagues/{league_id}/standings")
def get_standings(
    league_id: int,
    venue: str = Query("all"),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    league = db.query(League).get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    rows = (
        db.query(Standing)
        .filter(Standing.league_id == league_id, Standing.venue_type == venue)
        .order_by(Standing.group_name.nullsfirst(), Standing.position)
        .all()
    )
    logger.info("GET /leagues/%d/standings?venue=%s → %d rows", league_id, venue, len(rows))

    def _to_row(r: Standing) -> StandingRow:
        return StandingRow(
            position=r.position,
            team=TeamShort.model_validate(r.team),
            played=r.played,
            won=r.won,
            drawn=r.drawn,
            lost=r.lost,
            goals_for=r.goals_for,
            goals_against=r.goals_against,
            goal_difference=r.goal_difference,
            points=r.points,
        )

    if league.has_groups:
        # Group by group_name; keep insertion order (already sorted by group_name above)
        groups_dict: dict[str, list[StandingRow]] = {}
        for r in rows:
            gname = r.group_name or "Группа"
            groups_dict.setdefault(gname, []).append(_to_row(r))
        return StandingsResponse(
            groups=[StandingGroup(name=k, rows=v) for k, v in groups_dict.items()]
        )
    else:
        return StandingsResponse(rows=[_to_row(r) for r in rows])


@router.get("/leagues/{league_id}/advanced-stats", response_model=List[AdvancedStatsRow])
def get_advanced_stats(
    league_id: int,
    venue: str = Query("all"),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    league = db.query(League).get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    rows = compute_advanced_stats(db, league_id, venue)
    logger.info("GET /leagues/%d/advanced-stats?venue=%s → %d rows", league_id, venue, len(rows))
    return rows


@router.get("/leagues/{league_id}/smallmarkets", response_model=List[SmallMarketRow])
def get_smallmarkets(
    league_id: int,
    metric: str = Query("yellow_cards"),
    venue: str = Query("all"),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    league = db.query(League).get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if metric not in VALID_METRICS:
        logger.warning("Invalid metric %r, falling back to yellow_cards", metric)
        metric = "yellow_cards"
    rows = compute_smallmarket_stats(db, league_id, metric, venue)
    logger.info(
        "GET /leagues/%d/smallmarkets?metric=%s&venue=%s → %d rows",
        league_id, metric, venue, len(rows),
    )
    return rows


@router.get("/leagues/{league_id}/xg", response_model=List[XgRow])
def get_xg(
    league_id: int,
    venue: str = Query("all"),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    league = db.query(League).get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    user = access_svc.get_or_create_user(x_telegram_init_data, db)
    rows = compute_xg_stats(db, league_id, venue)
    access_svc.consume_premium_usage(db, user, "xg")
    logger.info("GET /leagues/%d/xg?venue=%s → %d rows", league_id, venue, len(rows))
    return rows


def _to_match_out(m: Match) -> MatchOut:
    dt = m.date or datetime.utcnow()
    date_str = dt.date().isoformat()
    time_str = dt.strftime("%H:%M")
    return MatchOut(
        id=m.id,
        date=date_str,
        time=time_str,
        home_team=TeamShort.model_validate(m.home_team),
        away_team=TeamShort.model_validate(m.away_team),
    )


def _team_stats_row(db: Session, league_id: int, team_id: int, venue: str) -> MatchTeamStats:
    standings_row = (
        db.query(Standing)
        .filter(
            Standing.league_id == league_id,
            Standing.team_id == team_id,
            Standing.venue_type == venue,
        )
        .first()
    )
    stats_rows = compute_advanced_stats(db, league_id, venue)
    current = next((r for r in stats_rows if r.team.id == team_id), None)
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return MatchTeamStats(
        position=standings_row.position if standings_row else 0,
        team=TeamShort.model_validate(team),
        srt=current.srt if current else 0.0,
        srt1=current.srt1 if current else 0.0,
        srt2=current.srt2 if current else 0.0,
        obz_pct=current.obz_pct if current else 0.0,
        matches=current.matches if current else 0,
        points=standings_row.points if standings_row else 0,
    )


@router.get("/leagues/{league_id}/matches", response_model=List[MatchOut])
def get_matches(
    league_id: int,
    days: int = Query(7, ge=1, le=30),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    league = db.query(League).get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    now = datetime.utcnow()
    max_dt = now + timedelta(days=days)

    rows = (
        db.query(Match)
        .filter(
            Match.league_id == league_id,
            Match.date.isnot(None),
            Match.date >= now,
            Match.date <= max_dt,
        )
        .order_by(Match.date.asc())
        .all()
    )
    if not rows:
        try:
            sync_upcoming_matches(db, league_id, days=days)
            rows = (
                db.query(Match)
                .filter(
                    Match.league_id == league_id,
                    Match.date.isnot(None),
                    Match.date >= now,
                    Match.date <= max_dt,
                )
                .order_by(Match.date.asc())
                .all()
            )
        except Exception as exc:
            logger.warning("Upcoming sync failed for league_id=%d: %s", league_id, exc)

    return [_to_match_out(m) for m in rows]


@router.get("/leagues/{league_id}/matches/{match_id}", response_model=MatchDetailOut)
def get_match_detail(
    league_id: int,
    match_id: int,
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    league = db.query(League).get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    match = db.query(Match).filter(Match.id == match_id, Match.league_id == league_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    general_home = _team_stats_row(db, league_id, match.home_team_id, "all")
    general_away = _team_stats_row(db, league_id, match.away_team_id, "all")
    by_position_home = _team_stats_row(db, league_id, match.home_team_id, "home")
    by_position_away = _team_stats_row(db, league_id, match.away_team_id, "away")

    return MatchDetailOut(
        match=_to_match_out(match),
        general_stats=[general_home, general_away],
        by_position_stats=[by_position_home, by_position_away],
    )


SMALLMARKET_LABELS = {
    "yellow_cards": "Жёлтые карточки",
    "corners": "Угловые",
    "shots_on_target": "Удары в створ",
    "shots_total": "Всего ударов",
    "fouls": "Фолы",
    "offsides": "Офсайды",
}


@router.get("/leagues/{league_id}/teams/{team_id}/profile", response_model=TeamProfileResponse)
def get_team_profile(
    league_id: int,
    team_id: int,
    venue: str = Query("all"),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    league = db.query(League).get(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    team = db.query(Team).filter(Team.id == team_id, Team.league_id == league_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    team_short = TeamShort.model_validate(team)

    # Summary (advanced stats for this team)
    adv_rows = compute_advanced_stats(db, league_id, venue)
    adv = next((r for r in adv_rows if r.team.id == team_id), None)
    summary = TeamProfileSummary(
        team=team_short,
        matches=adv.matches if adv else 0,
        srt=adv.srt if adv else 0.0,
        srt1=adv.srt1 if adv else 0.0,
        srt2=adv.srt2 if adv else 0.0,
        obz_pct=adv.obz_pct if adv else 0.0,
    )

    # Smallmarkets
    from app.services.stats import METRIC_COLUMNS
    smallmarkets = []
    for metric in METRIC_COLUMNS.keys():
        sm_rows = compute_smallmarket_stats(db, league_id, metric, venue)
        sm = next((r for r in sm_rows if r.team.id == team_id), None)
        smallmarkets.append(TeamSmallmarketMetric(
            metric=metric,
            label=SMALLMARKET_LABELS.get(metric, metric),
            srt=sm.srt if sm else 0.0,
            srt1=sm.srt1 if sm else 0.0,
            srt2=sm.srt2 if sm else 0.0,
        ))

    # xG is premium-only — available via GET /leagues/{id}/xg, not in free team profile.
    return TeamProfileResponse(
        team=team_short,
        summary=summary,
        smallmarkets=smallmarkets,
        xg=None,
    )


@router.get("/calculator/teams", response_model=List[TeamShort])
def calculator_teams(
    query: str = Query(""),
    leagueId: int | None = Query(None),
    limit: int = Query(80, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Teams for the calculator picker.
    - No leagueId: all leagues (for choosing home team), ordered by name.
    - leagueId set: restrict to that league (use for away team once home is chosen;
      calculator odds require both teams in the same league).
    """
    q = query.strip()
    teams_query = db.query(Team)
    if leagueId is not None:
        teams_query = teams_query.filter(Team.league_id == leagueId)
    if q:
        like = f"%{q}%"
        teams_query = teams_query.filter(
            Team.name.ilike(like) | Team.name_en.ilike(like)
        )
    teams = teams_query.order_by(Team.name.asc()).limit(limit).all()
    return [TeamShort.model_validate(t) for t in teams]


@router.get("/calculator/odds", response_model=CalculatorResult)
def calculator_odds(
    homeTeamId: int = Query(...),
    awayTeamId: int = Query(...),
    leagueId: int | None = Query(None),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if homeTeamId == awayTeamId:
        raise HTTPException(status_code=422, detail="homeTeamId and awayTeamId must differ")
    if leagueId is None:
        home_team = db.query(Team).filter(Team.id == homeTeamId).first()
        if not home_team:
            raise HTTPException(status_code=404, detail="Home team not found")
        leagueId = home_team.league_id
    user = access_svc.get_or_create_user(x_telegram_init_data, db)
    result = calculate_match_odds(db, leagueId, homeTeamId, awayTeamId)
    access_svc.consume_premium_usage(db, user, "calculator")
    return result
