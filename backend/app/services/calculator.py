import math
from typing import Dict, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import League, Match, MatchStatistics, Team, TeamMarketAggregate

GOALS_THRESHOLDS = [2.5, 3.5, 4.5]
CARDS_THRESHOLDS = [2.5, 3.5, 4.5, 5.5]
CORNERS_THRESHOLDS = [6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
MIN_SAMPLE = 5
EPSILON = 1e-9


def poisson_prob(lambda_value: float, k: int) -> float:
    if lambda_value < 0:
        return 0.0
    if k < 0:
        return 0.0
    return (lambda_value**k) * math.exp(-lambda_value) / math.factorial(k)


def score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> List[List[float]]:
    probs_home = [poisson_prob(lambda_home, i) for i in range(max_goals + 1)]
    probs_away = [poisson_prob(lambda_away, i) for i in range(max_goals + 1)]
    matrix: List[List[float]] = []
    for i in range(max_goals + 1):
        row: List[float] = []
        for j in range(max_goals + 1):
            row.append(probs_home[i] * probs_away[j])
        matrix.append(row)
    return matrix


def _to_percent(prob: float) -> float:
    return round(prob * 100, 3)


def _to_odds(prob: float) -> float:
    p = max(prob, EPSILON)
    return round(1.0 / p, 4)


def _calc_ou_rows_from_matrix(matrix: List[List[float]], thresholds: List[float]) -> List[Dict]:
    rows: List[Dict] = []
    for threshold in thresholds:
        floor_value = int(math.floor(threshold))
        under_prob = 0.0
        over_prob = 0.0
        for i, row in enumerate(matrix):
            for j, cell_prob in enumerate(row):
                if i + j <= floor_value:
                    under_prob += cell_prob
                else:
                    over_prob += cell_prob
        rows.append(
            {
                "event": f"ТБ {threshold}",
                "probability": _to_percent(over_prob),
                "odds": _to_odds(over_prob),
            }
        )
        rows.append(
            {
                "event": f"ТМ {threshold}",
                "probability": _to_percent(under_prob),
                "odds": _to_odds(under_prob),
            }
        )
    return rows


def _calc_ou_rows_from_total_lambda(lambda_total: float, thresholds: List[float], max_k: int = 25) -> List[Dict]:
    rows: List[Dict] = []
    dist = [poisson_prob(lambda_total, k) for k in range(max_k + 1)]
    for threshold in thresholds:
        floor_value = int(math.floor(threshold))
        under_prob = sum(dist[: floor_value + 1])
        over_prob = max(0.0, 1.0 - under_prob)
        rows.append(
            {
                "event": f"ТБ {threshold}",
                "probability": _to_percent(over_prob),
                "odds": _to_odds(over_prob),
            }
        )
        rows.append(
            {
                "event": f"ТМ {threshold}",
                "probability": _to_percent(under_prob),
                "odds": _to_odds(under_prob),
            }
        )
    return rows


def _team_market_aggregate(
    db: Session,
    league_id: int,
    season: int,
    team_id: int,
    venue_type: str,
    market: str,
) -> TeamMarketAggregate | None:
    return (
        db.query(TeamMarketAggregate)
        .filter(
            TeamMarketAggregate.league_id == league_id,
            TeamMarketAggregate.season == season,
            TeamMarketAggregate.team_id == team_id,
            TeamMarketAggregate.venue_type == venue_type,
            TeamMarketAggregate.market == market,
            TeamMarketAggregate.window_size == 0,
        )
        .first()
    )


def _fallback_market_from_matches(
    db: Session,
    league_id: int,
    season: int,
    team_id: int,
    venue_type: str,
    market: str,
) -> Tuple[float, float, int]:
    q = db.query(Match).filter(
        Match.league_id == league_id,
        Match.season == season,
        Match.status == "FT",
    )
    if venue_type == "home":
        q = q.filter(Match.home_team_id == team_id)
    elif venue_type == "away":
        q = q.filter(Match.away_team_id == team_id)
    else:
        q = q.filter((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
    matches = q.order_by(Match.date.desc()).all()

    if not matches:
        return 0.0, 0.0, 0

    for_total = 0.0
    against_total = 0.0
    if market == "goals":
        for match in matches:
            if match.home_team_id == team_id:
                for_total += float(match.home_goals or 0)
                against_total += float(match.away_goals or 0)
            else:
                for_total += float(match.away_goals or 0)
                against_total += float(match.home_goals or 0)
        n = len(matches)
        return for_total / n, against_total / n, n

    # Markets backed by MatchStatistics.
    stat_rows = (
        db.query(Match, MatchStatistics)
        .join(MatchStatistics, MatchStatistics.match_id == Match.id)
        .filter(Match.id.in_([m.id for m in matches]))
        .all()
    )
    if not stat_rows:
        return 0.0, 0.0, 0

    metric_map = {
        "yellow_cards": ("home_yellow_cards", "away_yellow_cards"),
        "corners": ("home_corners", "away_corners"),
    }
    home_col, away_col = metric_map[market]
    for match, stats in stat_rows:
        if match.home_team_id == team_id:
            for_total += float(getattr(stats, home_col) or 0)
            against_total += float(getattr(stats, away_col) or 0)
        else:
            for_total += float(getattr(stats, away_col) or 0)
            against_total += float(getattr(stats, home_col) or 0)
    n = len(stat_rows)
    return for_total / n, against_total / n, n


def _market_inputs(
    db: Session,
    league_id: int,
    season: int,
    home_team_id: int,
    away_team_id: int,
    market: str,
    league_key: str | None = None,
) -> Dict:
    venue_home = "all" if league_key == "world_cup" else "home"
    venue_away = "all" if league_key == "world_cup" else "away"

    home = _team_market_aggregate(db, league_id, season, home_team_id, venue_home, market)
    away = _team_market_aggregate(db, league_id, season, away_team_id, venue_away, market)

    if home and away:
        return {
            "home_for": float(home.avg_for),
            "home_against": float(home.avg_against),
            "home_n": int(home.matches_count),
            "away_for": float(away.avg_for),
            "away_against": float(away.avg_against),
            "away_n": int(away.matches_count),
        }

    home_for, home_against, home_n = _fallback_market_from_matches(
        db, league_id, season, home_team_id, venue_home, market
    )
    away_for, away_against, away_n = _fallback_market_from_matches(
        db, league_id, season, away_team_id, venue_away, market
    )
    return {
        "home_for": home_for,
        "home_against": home_against,
        "home_n": home_n,
        "away_for": away_for,
        "away_against": away_against,
        "away_n": away_n,
    }


def _insufficient_data_detail(league: League | None) -> str:
    if league and league.key == "world_cup":
        return (
            "Для ЧМ-2026 пока нет сыгранных матчей в базе. "
            "Калькулятор заработает после начала турнира."
        )
    return f"Недостаточно данных (нужно минимум {MIN_SAMPLE} матчей на команду дома/в гостях)"


def calculate_match_odds(db: Session, league_id: int, home_team_id: int, away_team_id: int) -> Dict:
    league = db.query(League).filter(League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    home = db.query(Team).filter(Team.id == home_team_id).first()
    away = db.query(Team).filter(Team.id == away_team_id).first()
    if not home or not away:
        raise HTTPException(status_code=404, detail="Team not found")
    if home.league_id != league_id or away.league_id != league_id:
        raise HTTPException(status_code=422, detail="Teams must belong to selected league")

    min_sample = 1 if league.key == "world_cup" else MIN_SAMPLE

    goals_input = _market_inputs(db, league_id, league.season, home_team_id, away_team_id, "goals", league.key)
    if min(goals_input["home_n"], goals_input["away_n"]) < min_sample:
        raise HTTPException(status_code=422, detail=_insufficient_data_detail(league))

    lambda_home = (goals_input["home_for"] + goals_input["away_against"]) / 2.0
    lambda_away = (goals_input["away_for"] + goals_input["home_against"]) / 2.0
    matrix = score_matrix(lambda_home, lambda_away, max_goals=10)

    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    for i, row in enumerate(matrix):
        for j, cell_prob in enumerate(row):
            if i > j:
                p_home += cell_prob
            elif i == j:
                p_draw += cell_prob
            else:
                p_away += cell_prob

    main_outcomes = [
        {"event": "П1", "subevent": "Хозяева", "probability": _to_percent(p_home), "odds": _to_odds(p_home)},
        {"event": "Х", "subevent": "Ничья", "probability": _to_percent(p_draw), "odds": _to_odds(p_draw)},
        {"event": "П2", "subevent": "Гости", "probability": _to_percent(p_away), "odds": _to_odds(p_away)},
    ]

    cards_input = _market_inputs(db, league_id, league.season, home_team_id, away_team_id, "yellow_cards", league.key)
    corners_input = _market_inputs(db, league_id, league.season, home_team_id, away_team_id, "corners", league.key)

    cards_rows: List[Dict]
    if min(cards_input["home_n"], cards_input["away_n"]) >= min_sample:
        lambda_cards = cards_input["home_for"] + cards_input["away_for"]
        cards_rows = _calc_ou_rows_from_total_lambda(lambda_cards, CARDS_THRESHOLDS)
    else:
        cards_rows = []

    corners_rows: List[Dict]
    if min(corners_input["home_n"], corners_input["away_n"]) >= min_sample:
        lambda_corners = corners_input["home_for"] + corners_input["away_for"]
        corners_rows = _calc_ou_rows_from_total_lambda(lambda_corners, CORNERS_THRESHOLDS)
    else:
        corners_rows = []

    sections = [
        {"id": "goals", "title": "Тотал голов", "rows": _calc_ou_rows_from_matrix(matrix, GOALS_THRESHOLDS)},
        {"id": "cards", "title": "Тотал желтых карточек", "rows": cards_rows},
        {"id": "corners", "title": "Тотал угловых", "rows": corners_rows},
    ]

    return {
        "home_team": home,
        "away_team": away,
        "main_outcomes": main_outcomes,
        "sections": sections,
    }
