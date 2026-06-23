from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from typing import List

from app.models import Match, MatchStatistics, MatchXG, Team
from app.schemas import AdvancedStatsRow, SmallMarketRow, XgRow, TeamShort


def _team_match_filter(team_id_col, venue: str):
    """Return filter conditions for a team based on venue type."""
    if venue == "home":
        return Match.home_team_id == team_id_col
    elif venue == "away":
        return Match.away_team_id == team_id_col
    return or_(Match.home_team_id == team_id_col, Match.away_team_id == team_id_col)


def compute_advanced_stats(db: Session, league_id: int, venue: str) -> List[AdvancedStatsRow]:
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    results = []

    for team in teams:
        if venue == "home":
            matches = db.query(Match).filter(
                Match.league_id == league_id, Match.home_team_id == team.id, Match.status == "FT"
            ).all()
        elif venue == "away":
            matches = db.query(Match).filter(
                Match.league_id == league_id, Match.away_team_id == team.id, Match.status == "FT"
            ).all()
        else:
            matches = db.query(Match).filter(
                Match.league_id == league_id,
                or_(Match.home_team_id == team.id, Match.away_team_id == team.id),
                Match.status == "FT",
            ).all()

        n = len(matches)
        if n == 0:
            results.append(AdvancedStatsRow(
                team=TeamShort.model_validate(team), matches=0,
                srt=0, srt1=0, srt2=0, obz_pct=0,
            ))
            continue

        goals_for = 0
        goals_against = 0
        btts = 0
        for m in matches:
            if m.home_team_id == team.id:
                gf, ga = m.home_goals, m.away_goals
            else:
                gf, ga = m.away_goals, m.home_goals
            goals_for += gf
            goals_against += ga
            if gf > 0 and ga > 0:
                btts += 1

        srt1 = round(goals_for / n, 2)
        srt2 = round(goals_against / n, 2)
        srt = round((goals_for + goals_against) / n, 2)
        obz = round(btts / n * 100, 1)

        results.append(AdvancedStatsRow(
            team=TeamShort.model_validate(team),
            matches=n, srt=srt, srt1=srt1, srt2=srt2, obz_pct=obz,
        ))

    results.sort(key=lambda r: r.srt, reverse=True)
    return results


METRIC_COLUMNS = {
    "yellow_cards": ("home_yellow_cards", "away_yellow_cards"),
    "corners": ("home_corners", "away_corners"),
    "shots_on_target": ("home_shots_on_target", "away_shots_on_target"),
    "shots_total": ("home_shots_total", "away_shots_total"),
    "fouls": ("home_fouls", "away_fouls"),
    "offsides": ("home_offsides", "away_offsides"),
}


def compute_smallmarket_stats(
    db: Session, league_id: int, metric: str, venue: str
) -> List[SmallMarketRow]:
    home_col_name, away_col_name = METRIC_COLUMNS[metric]
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    results = []

    for team in teams:
        query = (
            db.query(Match, MatchStatistics)
            .join(MatchStatistics, MatchStatistics.match_id == Match.id)
            .filter(Match.league_id == league_id, Match.status == "FT")
        )

        if venue == "home":
            query = query.filter(Match.home_team_id == team.id)
        elif venue == "away":
            query = query.filter(Match.away_team_id == team.id)
        else:
            query = query.filter(
                or_(Match.home_team_id == team.id, Match.away_team_id == team.id)
            )

        rows = query.all()
        n = len(rows)
        if n == 0:
            results.append(SmallMarketRow(
                team=TeamShort.model_validate(team), matches=0, srt=0, srt1=0, srt2=0,
            ))
            continue

        team_total = 0
        opp_total = 0
        for match, stats in rows:
            home_val = getattr(stats, home_col_name)
            away_val = getattr(stats, away_col_name)
            if match.home_team_id == team.id:
                team_total += home_val
                opp_total += away_val
            else:
                team_total += away_val
                opp_total += home_val

        srt1 = round(team_total / n, 1)
        srt2 = round(opp_total / n, 1)
        srt = round((team_total + opp_total) / n, 1)

        results.append(SmallMarketRow(
            team=TeamShort.model_validate(team), matches=n, srt=srt, srt1=srt1, srt2=srt2,
        ))

    results.sort(key=lambda r: r.srt, reverse=True)
    return results


def compute_xg_stats(db: Session, league_id: int, venue: str) -> List[XgRow]:
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    results = []

    for team in teams:
        query = (
            db.query(Match, MatchXG)
            .join(MatchXG, MatchXG.match_id == Match.id)
            .filter(Match.league_id == league_id, Match.status == "FT")
        )

        if venue == "home":
            query = query.filter(Match.home_team_id == team.id)
        elif venue == "away":
            query = query.filter(Match.away_team_id == team.id)
        else:
            query = query.filter(
                or_(Match.home_team_id == team.id, Match.away_team_id == team.id)
            )

        rows = query.all()
        n = len(rows)
        if n == 0:
            results.append(XgRow(
                team=TeamShort.model_validate(team),
                matches=0, xg=0, xga=0, delta_g=0, delta_ga=0,
            ))
            continue

        total_xg = 0.0
        total_xga = 0.0
        total_goals = 0
        total_conceded = 0
        for match, xg_data in rows:
            if match.home_team_id == team.id:
                total_xg += xg_data.home_xg
                total_xga += xg_data.away_xg
                total_goals += match.home_goals
                total_conceded += match.away_goals
            else:
                total_xg += xg_data.away_xg
                total_xga += xg_data.home_xg
                total_goals += match.away_goals
                total_conceded += match.home_goals

        delta_g = round((total_goals - total_xg) / n, 2)
        delta_ga = round((total_conceded - total_xga) / n, 2)

        results.append(XgRow(
            team=TeamShort.model_validate(team),
            matches=n,
            xg=round(total_xg / n, 2),
            xga=round(total_xga / n, 2),
            delta_g=delta_g,
            delta_ga=delta_ga,
        ))

    results.sort(key=lambda r: r.delta_g, reverse=True)
    return results
