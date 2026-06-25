"""
Sync service: loads real data from SStats.net into the local database.

Two main entry points:
  seed_league(db, sstats_league_id, year)  – one-time: creates league + teams
  sync_matches(db, league_id)              – refresh: loads games, stats, xG, standings
"""
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional, Dict

from sqlalchemy.orm import Session

from app.models import (
    League,
    Team,
    Match,
    MatchStatistics,
    MatchXG,
    Standing,
    TeamMarketAggregate,
    SyncRun,
)
from app.services.national_flags import national_flag_url
from app.services.sstats import (
    SSTATS_BASE,
    fetch_leagues_sync,
    find_league,
    find_current_season,
    fetch_standings_sync,
    fetch_all_games_sync,
    fetch_all_games_by_season_uid_sync,
    fetch_game_detail_sync,
    fetch_team_by_id,
    fetch_teams_sync,
    _throttle,
)

logger = logging.getLogger("sync")

FINISHED_STATUSES = {8, 9, 10, 17, 18}
UPCOMING_STATUSES = {1, 2}
MARKET_TO_COLUMNS = {
    "goals": ("home_goals", "away_goals"),
    "yellow_cards": ("home_yellow_cards", "away_yellow_cards"),
    "corners": ("home_corners", "away_corners"),
}

RUSSIAN_NAMES = {
    "Arsenal": "Арсенал",
    "Aston Villa": "Астон Вилла",
    "Bournemouth": "Борнмут",
    "Brentford": "Брентфорд",
    "Brighton": "Брайтон",
    "Chelsea": "Челси",
    "Crystal Palace": "Кристал Пэлас",
    "Everton": "Эвертон",
    "Fulham": "Фулхэм",
    "Ipswich": "Ипсвич Таун",
    "Ipswich Town": "Ипсвич Таун",
    "Leicester": "Лестер Сити",
    "Leicester City": "Лестер Сити",
    "Liverpool": "Ливерпуль",
    "Manchester City": "Манчестер Сити",
    "Manchester United": "Манчестер Юнайтед",
    "Newcastle": "Ньюкасл",
    "Nottingham Forest": "Ноттингем Форест",
    "Nott. Forest": "Ноттингем Форест",
    "Southampton": "Саутгемптон",
    "Tottenham": "Тоттенхэм",
    "West Ham": "Вест Хэм",
    "Wolverhampton": "Вулверхэмптон",
    "Wolves": "Вулверхэмптон",
    "Burnley": "Бёрнли",
    "Leeds": "Лидс",
    "Leeds United": "Лидс Юнайтед",
    "Sunderland": "Сандерленд",
    "Luton": "Лутон Таун",
    "Luton Town": "Лутон Таун",
    "Sheffield United": "Шеффилд Юнайтед",
    "Sheffield Utd": "Шеффилд Юнайтед",
    # National teams (World Cup)
    "Argentina": "Аргентина",
    "Australia": "Австралия",
    "Belgium": "Бельгия",
    "Bosnia and Herzegovina": "Босния и Герцеговина",
    "Brazil": "Бразилия",
    "Canada": "Канада",
    "Cameroon": "Камерун",
    "Chile": "Чили",
    "Colombia": "Колумбия",
    "Costa Rica": "Коста-Рика",
    "Croatia": "Хорватия",
    "Czech Republic": "Чехия",
    "Denmark": "Дания",
    "Ecuador": "Эквадор",
    "England": "Англия",
    "France": "Франция",
    "Germany": "Германия",
    "Ghana": "Гана",
    "Haiti": "Гаити",
    "Iran": "Иран",
    "Italy": "Италия",
    "Japan": "Япония",
    "Mexico": "Мексика",
    "Morocco": "Марокко",
    "Netherlands": "Нидерланды",
    "New Zealand": "Новая Зеландия",
    "Nigeria": "Нигерия",
    "Panama": "Панама",
    "Paraguay": "Парагвай",
    "Peru": "Перу",
    "Poland": "Польша",
    "Portugal": "Португалия",
    "Qatar": "Катар",
    "Romania": "Румыния",
    "Russia": "Россия",
    "Saudi Arabia": "Саудовская Аравия",
    "Scotland": "Шотландия",
    "Senegal": "Сенегал",
    "Serbia": "Сербия",
    "Slovakia": "Словакия",
    "South Africa": "ЮАР",
    "South Korea": "Южная Корея",
    "Spain": "Испания",
    "Switzerland": "Швейцария",
    "Tunisia": "Тунис",
    "Turkey": "Турция",
    "Ukraine": "Украина",
    "United States": "США",
    "Uruguay": "Уругвай",
    "Venezuela": "Венесуэла",
    "Wales": "Уэльс",
    "Bosnia & Herzegovina": "Босния и Герцеговина",
    "Curaçao": "Кюрасао",
    "Ivory Coast": "Кот-д'Ивуар",
    "USA": "США",
    "Türkiye": "Турция",
    "Sweden": "Швеция",
    "Egypt": "Египет",
    "Austria": "Австрия",
    "Norway": "Норвегия",
    "Congo DR": "ДР Конго",
    "Algeria": "Алжир",
    "Cape Verde Islands": "Кабо-Верде",
    "Jordan": "Иордания",
    "Iraq": "Ирак",
    "Uzbekistan": "Узбекистан",
    "Greece": "Греция",
    "Slovenia": "Словения",
    "Hungary": "Венгрия",
    "Albania": "Албания",
    "Georgia": "Грузия",
    "Finland": "Финляндия",
    "Iceland": "Исландия",
    "Northern Ireland": "Северная Ирландия",
    "Republic of Ireland": "Ирландия",
    "Ireland": "Ирландия",
    "China": "Китай",
    "Syria": "Сирия",
    "Oman": "Оман",
    "Bahrain": "Бахрейн",
    "Palestine": "Палестина",
    "Kyrgyzstan": "Киргизия",
    "Tajikistan": "Таджикистан",
    "Thailand": "Таиланд",
    "Vietnam": "Вьетнам",
    "North Korea": "КНДР",
    "India": "Индия",
    "Mali": "Мали",
    "Burkina Faso": "Буркина-Фасо",
    "South Sudan": "Южный Судан",
    "Sudan": "Судан",
    "Guinea": "Гвинея",
    "Uganda": "Уганда",
    "Benin": "Бенин",
    "Zambia": "Замбия",
    "Kenya": "Кения",
    "Togo": "Того",
    "Angola": "Ангола",
    "Libya": "Ливия",
    "Mauritania": "Мавритания",
    "Madagascar": "Мадагаскар",
    "Mozambique": "Мозамбик",
    "Honduras": "Гондурас",
    "El Salvador": "Сальвадор",
    "Jamaica": "Ямайка",
    "Trinidad and Tobago": "Тринидад и Тобаго",
    "Trinidad & Tobago": "Тринидад и Тобаго",
    "Guatemala": "Гватемала",
    "Bolivia": "Боливия",
}


def _is_world_cup(league: League) -> bool:
    return league.key == "world_cup"


def _normalize_world_cup_group_name(group_name: Optional[str]) -> Optional[str]:
    """Return localized World Cup group names and skip aggregate tables."""
    if not group_name:
        return None
    raw = group_name.strip()
    lowered = raw.lower()
    for prefix in ("group ", "группа "):
        if lowered.startswith(prefix):
            suffix = raw[len(prefix):].strip()
            if len(suffix) == 1 and suffix.isalpha():
                return f"Группа {suffix.upper()}"
    return None


def _game_db_status(status: int) -> Optional[str]:
    if status in FINISHED_STATUSES:
        return "FT"
    if status in UPCOMING_STATUSES:
        return "NS"
    return None


def _safe_int(val, default=0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _start_sync_run(db: Session, source: str, league: League) -> SyncRun:
    run = SyncRun(
        source=source,
        league_id=league.id,
        season=league.season or 0,
        started_at=_utcnow(),
        status="running",
        rows_written=0,
    )
    db.add(run)
    db.flush()
    return run


def _finish_sync_run(
    db: Session,
    run: SyncRun,
    rows_written: int,
    error: Optional[str] = None,
):
    run.finished_at = _utcnow()
    run.rows_written = rows_written
    if error:
        run.status = "failed"
        run.error = error[:1000]
    else:
        run.status = "ok"


def _logo_url(team_dict: dict) -> Optional[str]:
    """
    Normalize logo URL from SStats:
    - primary: data.logoUrl (Teams/list, Teams/{id} as per schema)
    - fallback: data.team.logoUrl (in case of alternative response shapes)
    - keep absolute https URLs as-is
    - upgrade http→https to avoid mixed content in browser
    - expand relative paths using SSTATS_BASE
    """
    raw = team_dict.get("logoUrl") or (team_dict.get("team") or {}).get("logoUrl")
    if not raw:
        return None

    url = str(raw)
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    if url.startswith("/"):
        return f"{SSTATS_BASE}{url}"
    return url


def _is_non_country_league_country(country: Optional[str]) -> bool:
    """
    UEFA club tournaments use country name World/Europe on /Leagues.
    /Teams/list?Country=World returns national teams, not clubs — skip bulk list.
    """
    if not country:
        return False
    n = country.strip().lower()
    return n in ("world", "europe") or n == "international"


def _enrich_team_logo_from_list(api_team: dict, sstats_tid: int) -> dict:
    """
    GET /Teams/{id} often omits logoUrl; GET /Teams/list with Name+Country includes it.
    Used for intercontinental leagues and whenever the detail payload has no logo.
    """
    if _logo_url(api_team):
        return api_team
    country = (api_team.get("country") or {}).get("name")
    name = api_team.get("name")
    if not country or not name:
        return api_team
    name_str = str(name).strip()
    if len(name_str) < 2:
        return api_team
    _throttle()
    rows = fetch_teams_sync(name=name_str, country=country, limit=100)
    for t in rows:
        try:
            if int(t.get("id")) != sstats_tid:
                continue
        except (TypeError, ValueError):
            continue
        raw_logo = t.get("logoUrl")
        if not raw_logo:
            return api_team
        merged = dict(api_team)
        merged["logoUrl"] = raw_logo
        return merged
    return api_team


# ─── Seed league + teams ─────────────────────────────────────────────────────

def seed_league(
    db: Session,
    sstats_league_id: int = 39,
    year: Optional[int] = None,
    league_name_ru: Optional[str] = None,
    league_key: Optional[str] = None,
) -> Optional[League]:
    """
    Fetch league metadata + current season from SStats, create League and Team rows.
    Returns the League ORM object or None on failure.
    """
    all_leagues = fetch_leagues_sync()
    if not all_leagues:
        logger.error("Failed to fetch leagues from SStats")
        return None

    lg_data = find_league(all_leagues, sstats_league_id)
    if not lg_data:
        logger.error("League sstats_id=%d not found", sstats_league_id)
        return None

    season_data = find_current_season(lg_data, year)
    if not season_data:
        logger.error("No season found for league=%d year=%s", sstats_league_id, year)
        return None

    season_year = season_data["year"]
    season_uid = season_data["uid"]
    country_name = (lg_data.get("country") or {}).get("name", "")

    # World Cup uses groups
    is_world_cup = league_key == "world_cup"
    has_groups = is_world_cup

    existing = db.query(League).filter(League.sstats_id == sstats_league_id).first()
    if existing:
        existing.season = season_year
        existing.season_uid = season_uid
        if league_name_ru:
            existing.name = league_name_ru
        existing.name_en = lg_data.get("name") or existing.name_en
        if league_key:
            existing.key = league_key
        if is_world_cup:
            existing.has_groups = True
        league = existing
        logger.info("Updated existing league id=%d season=%d", league.id, season_year)
    else:
        league = League(
            key=league_key,
            name=league_name_ru or lg_data["name"],
            name_en=lg_data["name"],
            sstats_id=sstats_league_id,
            api_football_id=sstats_league_id,
            country=country_name,
            has_groups=has_groups,
            season=season_year,
            season_uid=season_uid,
        )
        db.add(league)
        db.flush()
        logger.info("Created league id=%d name=%s season=%d", league.id, lg_data["name"], season_year)

    _seed_teams_from_standings(db, league, season_uid)
    if (
        is_world_cup
        and db.query(Team).filter(Team.league_id == league.id).count() == 0
    ):
        _seed_teams_from_games(db, league)
    db.commit()
    return league


def _resolve_team_logo(league: League, name_en: str, api_team: Optional[dict]) -> Optional[str]:
    logo = _logo_url(api_team) if api_team else None
    if not logo and _is_world_cup(league):
        logo = national_flag_url(name_en)
    return logo


def _upsert_team(
    db: Session,
    league: League,
    sstats_tid: int,
    api_team: Optional[dict] = None,
) -> Team:
    existing = db.query(Team).filter(
        Team.sstats_id == sstats_tid,
        Team.league_id == league.id,
    ).first()

    if not api_team:
        api_team = fetch_team_by_id(sstats_tid)
    if api_team:
        api_team = _enrich_team_logo_from_list(api_team, sstats_tid)

    if existing:
        if api_team:
            name_en = api_team.get("name") or existing.name_en
            logo = _resolve_team_logo(league, name_en, api_team)
            if logo:
                existing.logo_url = logo
            if api_team.get("name"):
                existing.name_en = api_team.get("name")
                existing.name = RUSSIAN_NAMES.get(existing.name_en, existing.name_en)
        return existing

    if api_team:
        name_en = api_team.get("name", f"Team {sstats_tid}")
        name_ru = RUSSIAN_NAMES.get(name_en, name_en)
        logo = _resolve_team_logo(league, name_en, api_team)
    else:
        name_en = f"Team {sstats_tid}"
        name_ru = name_en
        logo = None
        logger.warning("Team sstats_id=%d not found via /Teams/{id}", sstats_tid)

    team = Team(
        name=name_ru,
        name_en=name_en,
        sstats_id=sstats_tid,
        api_football_id=sstats_tid,
        sstats_name=name_en.lower(),
        logo_url=logo,
        league_id=league.id,
    )
    db.add(team)
    db.flush()
    logger.info("Created team: %s (sstats_id=%d)", name_en, sstats_tid)
    return team


def _seed_teams_from_games(db: Session, league: League):
    """
    World Cup fallback: SStats often returns empty /Seasons/standings.
    Extract national teams from /Games/list for the season.
    """
    if not league.season_uid:
        logger.error("Cannot seed teams from games: league %d has no season_uid", league.id)
        return

    games = fetch_all_games_by_season_uid_sync(season_uid=league.season_uid)
    if not games:
        logger.warning("No games returned for season_uid=%s", league.season_uid)
        return

    team_stubs: Dict[int, dict] = {}
    for game in games:
        for side in ("homeTeam", "awayTeam"):
            stub = game.get(side) or {}
            tid = _safe_int(stub.get("id"))
            if tid:
                team_stubs[tid] = stub

    logger.info("Found %d teams in games list", len(team_stubs))
    for sstats_tid, stub in team_stubs.items():
        _upsert_team(db, league, sstats_tid, api_team=stub)

    db.flush()


def _seed_teams_from_standings(db: Session, league: League, season_uid: str):
    """
    Extract team IDs from standings and create/update Team rows.
    Fetches team details via /Teams/list (by country) for logos and metadata.
    """
    standings_data = fetch_standings_sync(season_uid)
    if not standings_data:
        logger.error("Failed to fetch standings for season_uid=%s", season_uid)
        return

    tables = standings_data.get("tables") or []
    if not tables:
        logger.warning("No tables in standings for season_uid=%s", season_uid)
        return

    team_ids_from_standings = []
    for table in tables:
        for row in table.get("rows", []):
            tid = row.get("teamId")
            if tid:
                team_ids_from_standings.append(int(tid))

    logger.info("Found %d teams in standings", len(team_ids_from_standings))

    # Fetch teams catalog from /Teams/list filtered by country (to get logoUrl).
    # Skip when league "country" is World/Europe — that list is not club teams.
    country = league.country or None
    if country and _is_non_country_league_country(country):
        api_teams = []
        logger.info(
            "Skipping /Teams/list for country=%r (intercontinental league; per-team logo)",
            country,
        )
    elif country:
        api_teams = fetch_teams_sync(country=country)
    else:
        api_teams = fetch_teams_sync()
    if not api_teams:
        logger.warning("No teams returned from /Teams/list for country=%r", country)
        api_teams_by_id: Dict[int, dict] = {}
    else:
        api_teams_by_id = {}
        for t in api_teams:
            try:
                tid = int(t.get("id"))
            except (TypeError, ValueError):
                continue
            api_teams_by_id[tid] = t
        logger.info(
            "Loaded %d teams from /Teams/list (country=%r)",
            len(api_teams_by_id),
            country,
        )

    for sstats_tid in team_ids_from_standings:
        api_team = api_teams_by_id.get(sstats_tid)
        if not api_team:
            api_team = fetch_team_by_id(sstats_tid)
        _upsert_team(db, league, sstats_tid, api_team=api_team)

    db.flush()


# ─── Sync matches + statistics ────────────────────────────────────────────────

def sync_matches(
    db: Session,
    league_id: int,
    fetch_stats: bool = True,
) -> int:
    """
    Fetch all ended games from /Games/list and upsert Match rows.
    If fetch_stats=True, for each new match also fetch /Games/{id} and fill MatchStatistics + MatchXG.
    With API key, client throttles ~0.5s between requests (see sstats._throttle); without key ~2s.
    Returns count of new matches inserted.
    """
    league = db.query(League).get(league_id)
    if not league or not league.sstats_id or not league.season:
        logger.error("League %s not properly configured for sync", league_id)
        return 0

    team_map = _build_team_map(db, league_id)
    if not team_map:
        logger.error("No teams found for league_id=%d", league_id)
        return 0

    run = _start_sync_run(db, source="sync_matches", league=league)
    rows_written = 0
    try:
        if _is_world_cup(league) and league.season_uid:
            games = fetch_all_games_by_season_uid_sync(season_uid=league.season_uid)
        elif league.season_uid:
            games = fetch_all_games_by_season_uid_sync(season_uid=league.season_uid, ended=True)
        else:
            games = fetch_all_games_sync(league.sstats_id, league.season)
        logger.info("Fetched %d games from API for league=%d season=%d", len(games), league_id, league.season)

        existing_by_sstats_id = {
            m.sstats_id: m
            for m in db.query(Match).filter(
                Match.league_id == league_id,
                Match.sstats_id.isnot(None),
            ).all()
        }

        new_count = 0
        for game in games:
            sstats_gid = _safe_int(game.get("id"))
            if not sstats_gid:
                continue

            status = _safe_int(game.get("status"))
            match_status = _game_db_status(status)
            if not match_status:
                continue

            home_team = game.get("homeTeam") or {}
            away_team = game.get("awayTeam") or {}
            home_sstats_id = _safe_int(home_team.get("id"))
            away_sstats_id = _safe_int(away_team.get("id"))

            if _is_world_cup(league):
                if home_sstats_id and home_sstats_id not in team_map:
                    _upsert_team(db, league, home_sstats_id, api_team=home_team)
                if away_sstats_id and away_sstats_id not in team_map:
                    _upsert_team(db, league, away_sstats_id, api_team=away_team)
                team_map = _build_team_map(db, league_id)

            home_tid = team_map.get(home_sstats_id)
            away_tid = team_map.get(away_sstats_id)

            if not home_tid or not away_tid:
                logger.debug(
                    "Skipping game %d: unmapped teams home=%s away=%s",
                    sstats_gid, home_team.get("id"), away_team.get("id"),
                )
                continue

            date_str = game.get("date")
            match_date = None
            if date_str:
                try:
                    match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, TypeError):
                    pass

            existing = existing_by_sstats_id.get(sstats_gid)
            if existing:
                existing.home_team_id = home_tid
                existing.away_team_id = away_tid
                existing.home_goals = _safe_int(game.get("homeFTResult")) if match_status == "FT" else None
                existing.away_goals = _safe_int(game.get("awayFTResult")) if match_status == "FT" else None
                existing.date = match_date
                existing.status = match_status
                existing.round = game.get("roundName")
                match = existing
                rows_written += 1
            else:
                match = Match(
                    league_id=league_id,
                    season=league.season,
                    sstats_id=sstats_gid,
                    home_team_id=home_tid,
                    away_team_id=away_tid,
                    home_goals=_safe_int(game.get("homeFTResult")) if match_status == "FT" else None,
                    away_goals=_safe_int(game.get("awayFTResult")) if match_status == "FT" else None,
                    date=match_date,
                    status=match_status,
                    round=game.get("roundName"),
                )
                db.add(match)
                db.flush()
                new_count += 1
                rows_written += 1

            if fetch_stats and match_status == "FT":
                _fetch_and_save_stats(db, match, sstats_gid)

            if new_count % 50 == 0 and new_count > 0:
                logger.info("Progress: %d new matches synced…", new_count)

        recompute_team_market_aggregates(db, league_id)
        _finish_sync_run(db, run, rows_written=rows_written)
        db.commit()
        logger.info("Sync complete: %d new matches for league_id=%d", new_count, league_id)
        return new_count
    except Exception as exc:
        _finish_sync_run(db, run, rows_written=rows_written, error=str(exc))
        db.commit()
        raise


def sync_missing_stats(db: Session, league_id: int) -> int:
    """
    For matches that have no MatchStatistics, fetch /Games/{id} and fill MatchStatistics + MatchXG.
    Used after sync_matches(fetch_stats=False) to fill stats in background.
    Only finished matches are eligible; upcoming fixtures often have no detail stats yet.
    Returns number of matches filled.
    """
    league = db.query(League).get(league_id)
    if not league:
        return 0

    match_ids_with_stats = {r for (r,) in db.query(MatchStatistics.match_id).distinct().all()}
    q = db.query(Match).filter(
        Match.league_id == league_id,
        Match.sstats_id.isnot(None),
        Match.status == "FT",
    )
    if match_ids_with_stats:
        q = q.filter(~Match.id.in_(match_ids_with_stats))
    matches_without_stats = q.all()
    if not matches_without_stats:
        logger.info("No matches missing stats for league_id=%d", league_id)
        return 0

    filled = 0
    for match in matches_without_stats:
        _fetch_and_save_stats(db, match, match.sstats_id)
        filled += 1
        if filled % 50 == 0:
            logger.info("Filled stats for %d matches…", filled)
            db.commit()

    db.commit()
    logger.info("Filled stats for %d matches (league_id=%d)", filled, league_id)
    return filled


def _build_team_map(db: Session, league_id: int) -> Dict[int, int]:
    """Map sstats team id → internal team id."""
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    return {t.sstats_id: t.id for t in teams if t.sstats_id}


def _fetch_and_save_stats(db: Session, match: Match, sstats_game_id: int):
    """Fetch /Games/{id} detail and populate MatchStatistics + MatchXG."""
    detail = fetch_game_detail_sync(sstats_game_id)
    if not detail:
        logger.debug("No detail for game %d", sstats_game_id)
        return

    stats_data = detail.get("statistics")
    if stats_data:
        ms = db.query(MatchStatistics).filter(MatchStatistics.match_id == match.id).first()
        if not ms:
            ms = MatchStatistics(match_id=match.id)
            db.add(ms)
        ms.home_yellow_cards = _safe_int(stats_data.get("yellowCardsHome"))
        ms.away_yellow_cards = _safe_int(stats_data.get("yellowCardsAway"))
        ms.home_corners = _safe_int(stats_data.get("cornerKicksHome"))
        ms.away_corners = _safe_int(stats_data.get("cornerKicksAway"))
        ms.home_shots_on_target = _safe_int(stats_data.get("shotsOnGoalHome"))
        ms.away_shots_on_target = _safe_int(stats_data.get("shotsOnGoalAway"))
        ms.home_shots_total = _safe_int(stats_data.get("totalShotsHome"))
        ms.away_shots_total = _safe_int(stats_data.get("totalShotsAway"))
        ms.home_fouls = _safe_int(stats_data.get("foulsHome"))
        ms.away_fouls = _safe_int(stats_data.get("foulsAway"))
        ms.home_offsides = _safe_int(stats_data.get("offsidesHome"))
        ms.away_offsides = _safe_int(stats_data.get("offsidesAway"))

        home_xg = _safe_float(stats_data.get("expectedGoalsHome"))
        away_xg = _safe_float(stats_data.get("expectedGoalsAway"))
        xg = db.query(MatchXG).filter(MatchXG.match_id == match.id).first()
        if not xg:
            xg = MatchXG(match_id=match.id)
            db.add(xg)
        xg.home_xg = home_xg
        xg.away_xg = away_xg


# ─── Sync standings ──────────────────────────────────────────────────────────

def _team_names_from_games(games: list[dict]) -> dict[int, str]:
    names: dict[int, str] = {}
    for game in games:
        for side in ("homeTeam", "awayTeam"):
            stub = game.get(side) or {}
            tid = _safe_int(stub.get("id"))
            if tid:
                names[tid] = str(stub.get("name") or tid)
    return names


def _infer_world_cup_groups(games: list[dict]) -> dict[int, str]:
    """Cluster teams into groups using group-stage fixtures (union-find)."""
    parent: dict[int, int] = {}
    team_ids: set[int] = set()

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for game in games:
        rnd = (game.get("roundName") or "").lower()
        if "group stage" not in rnd:
            continue
        home_id = _safe_int((game.get("homeTeam") or {}).get("id"))
        away_id = _safe_int((game.get("awayTeam") or {}).get("id"))
        if not home_id or not away_id:
            continue
        team_ids.add(home_id)
        team_ids.add(away_id)
        parent.setdefault(home_id, home_id)
        parent.setdefault(away_id, away_id)
        union(home_id, away_id)

    clusters: dict[int, list[int]] = defaultdict(list)
    for tid in team_ids:
        clusters[find(tid)].append(tid)

    names = _team_names_from_games(games)
    sorted_clusters = sorted(
        clusters.values(),
        key=lambda members: min(names.get(tid, str(tid)) for tid in members),
    )

    group_map: dict[int, str] = {}
    for idx, members in enumerate(sorted_clusters):
        group_name = f"Группа {chr(ord('A') + idx)}"
        for tid in members:
            group_map[tid] = group_name
    return group_map


def _sync_world_cup_standings_from_games(
    db: Session,
    league: League,
    team_map: Dict[int, int],
) -> int:
    """
    Build grouped standings from local matches when /Seasons/standings is empty.
    """
    if not league.season_uid:
        return 0

    games = fetch_all_games_by_season_uid_sync(season_uid=league.season_uid)
    group_by_sstats = _infer_world_cup_groups(games)
    if not group_by_sstats:
        logger.warning("Could not infer World Cup groups from games")
        return 0

    internal_to_group: dict[int, str] = {}
    for sstats_tid, group_name in group_by_sstats.items():
        internal_tid = team_map.get(sstats_tid)
        if internal_tid:
            internal_to_group[internal_tid] = group_name

    teams_by_group: dict[str, list[int]] = defaultdict(list)
    for internal_tid, group_name in internal_to_group.items():
        teams_by_group[group_name].append(internal_tid)

    db.query(Standing).filter(Standing.league_id == league.id).delete()
    row_count = 0

    matches = (
        db.query(Match)
        .filter(
            Match.league_id == league.id,
            Match.season == league.season,
            Match.status == "FT",
        )
        .all()
    )

    for venue_type in ("all", "home", "away"):
        for group_name, team_ids in sorted(teams_by_group.items()):
            stats: dict[int, dict] = {
                tid: {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "pts": 0}
                for tid in team_ids
            }

            for m in matches:
                if "group stage" not in (m.round or "").lower():
                    continue
                home_group = internal_to_group.get(m.home_team_id)
                away_group = internal_to_group.get(m.away_team_id)
                if home_group != group_name or away_group != group_name:
                    continue

                if venue_type == "home":
                    tid = m.home_team_id
                    gf, ga = m.home_goals or 0, m.away_goals or 0
                elif venue_type == "away":
                    tid = m.away_team_id
                    gf, ga = m.away_goals or 0, m.home_goals or 0
                else:
                    for tid_side, gf_side, ga_side in (
                        (m.home_team_id, m.home_goals or 0, m.away_goals or 0),
                        (m.away_team_id, m.away_goals or 0, m.home_goals or 0),
                    ):
                        if tid_side not in stats:
                            continue
                        s = stats[tid_side]
                        s["played"] += 1
                        s["gf"] += gf_side
                        s["ga"] += ga_side
                        if gf_side > ga_side:
                            s["won"] += 1
                            s["pts"] += 3
                        elif gf_side == ga_side:
                            s["drawn"] += 1
                            s["pts"] += 1
                        else:
                            s["lost"] += 1
                    continue

                if tid not in stats:
                    continue
                s = stats[tid]
                s["played"] += 1
                s["gf"] += gf
                s["ga"] += ga
                if gf > ga:
                    s["won"] += 1
                    s["pts"] += 3
                elif gf == ga:
                    s["drawn"] += 1
                    s["pts"] += 1
                else:
                    s["lost"] += 1

            team_name_by_id = {
                t.id: t.name_en
                for t in db.query(Team).filter(Team.id.in_(team_ids)).all()
            }
            sorted_tids = sorted(
                team_ids,
                key=lambda tid: (
                    -stats[tid]["pts"],
                    -(stats[tid]["gf"] - stats[tid]["ga"]),
                    -stats[tid]["gf"],
                    team_name_by_id.get(tid, ""),
                ),
            )

            for pos, tid in enumerate(sorted_tids, 1):
                s = stats[tid]
                db.add(
                    Standing(
                        team_id=tid,
                        league_id=league.id,
                        season=league.season,
                        venue_type=venue_type,
                        group_name=group_name,
                        position=pos,
                        played=s["played"],
                        won=s["won"],
                        drawn=s["drawn"],
                        lost=s["lost"],
                        goals_for=s["gf"],
                        goals_against=s["ga"],
                        goal_difference=s["gf"] - s["ga"],
                        points=s["pts"],
                    )
                )
                row_count += 1

    db.commit()
    logger.info(
        "World Cup standings synced from games: %d rows for league_id=%d",
        row_count,
        league.id,
    )
    return row_count


def sync_standings(db: Session, league_id: int) -> int:
    """
    Fetch /Seasons/standings and upsert Standing rows (all venue_type).
    Returns number of rows written.
    """
    league = db.query(League).get(league_id)
    if not league or not league.season_uid:
        logger.error("League %d missing season_uid", league_id)
        return 0

    team_map = _build_team_map(db, league_id)
    if not team_map:
        logger.error("No teams for league_id=%d", league_id)
        return 0

    standings_data = fetch_standings_sync(league.season_uid)
    tables = (standings_data or {}).get("tables") or []

    if _is_world_cup(league) and not tables:
        return _sync_world_cup_standings_from_games(db, league, team_map)

    if not standings_data:
        logger.error("Failed to fetch standings for league_id=%d", league_id)
        return 0

    db.query(Standing).filter(Standing.league_id == league_id).delete()

    row_count = 0

    for table in tables:
        rows = table.get("rows") or []
        for api_row in rows:
            group_name = api_row.get("groupName")
            if _is_world_cup(league):
                group_name = _normalize_world_cup_group_name(group_name)
                if not group_name:
                    continue
            sstats_tid = _safe_int(api_row.get("teamId"))
            internal_tid = team_map.get(sstats_tid)
            if not internal_tid:
                continue

            standing = Standing(
                team_id=internal_tid,
                league_id=league_id,
                season=league.season,
                venue_type="all",
                group_name=group_name,
                position=_safe_int(api_row.get("rank")),
                played=_safe_int(api_row.get("played")),
                won=_safe_int(api_row.get("wins")),
                drawn=_safe_int(api_row.get("draws")),
                lost=_safe_int(api_row.get("loses")),
                goals_for=_safe_int(api_row.get("goalsFor")),
                goals_against=_safe_int(api_row.get("goalsAgainst")),
                goal_difference=_safe_int(api_row.get("goalsFor")) - _safe_int(api_row.get("goalsAgainst")),
                points=_safe_int(api_row.get("points")),
            )
            db.add(standing)
            row_count += 1

    _compute_venue_standings(db, league_id, league.season)

    db.commit()
    logger.info("Standings synced: %d 'all' rows + home/away for league_id=%d", row_count, league_id)
    return row_count


def _compute_venue_standings(db: Session, league_id: int, season: int):
    """Compute home and away standings from matches in the database."""
    teams = db.query(Team).filter(Team.league_id == league_id).all()

    for venue_type in ["home", "away"]:
        stats = {}
        for team in teams:
            stats[team.id] = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "pts": 0}

        matches = db.query(Match).filter(
            Match.league_id == league_id,
            Match.season == season,
            Match.status == "FT",
        ).all()

        for m in matches:
            if venue_type == "home":
                tid = m.home_team_id
                gf, ga = m.home_goals or 0, m.away_goals or 0
            else:
                tid = m.away_team_id
                gf, ga = m.away_goals or 0, m.home_goals or 0

            if tid not in stats:
                continue
            s = stats[tid]
            s["played"] += 1
            s["gf"] += gf
            s["ga"] += ga
            if gf > ga:
                s["won"] += 1
                s["pts"] += 3
            elif gf == ga:
                s["drawn"] += 1
                s["pts"] += 1
            else:
                s["lost"] += 1

        sorted_tids = sorted(
            stats.keys(),
            key=lambda tid: (stats[tid]["pts"], stats[tid]["gf"] - stats[tid]["ga"], stats[tid]["gf"]),
            reverse=True,
        )
        for pos, tid in enumerate(sorted_tids, 1):
            s = stats[tid]
            standing = Standing(
                team_id=tid,
                league_id=league_id,
                season=season,
                venue_type=venue_type,
                position=pos,
                played=s["played"],
                won=s["won"],
                drawn=s["drawn"],
                lost=s["lost"],
                goals_for=s["gf"],
                goals_against=s["ga"],
                goal_difference=s["gf"] - s["ga"],
                points=s["pts"],
            )
            db.add(standing)


# ─── Aggregates for calculator ─────────────────────────────────────────────────

def recompute_team_market_aggregates(db: Session, league_id: int, window_size: int = 0) -> int:
    """
    Recompute per-team aggregates used by the calculator.
    window_size=0 means full season.
    """
    league = db.query(League).get(league_id)
    if not league:
        return 0

    teams = db.query(Team).filter(Team.league_id == league_id).all()
    if not teams:
        return 0

    db.query(TeamMarketAggregate).filter(
        TeamMarketAggregate.league_id == league_id,
        TeamMarketAggregate.season == league.season,
        TeamMarketAggregate.window_size == window_size,
    ).delete()

    written = 0
    now = _utcnow()
    for team in teams:
        rows = (
            db.query(Match, MatchStatistics)
            .join(MatchStatistics, MatchStatistics.match_id == Match.id)
            .filter(
                Match.league_id == league_id,
                Match.season == league.season,
                Match.status == "FT",
                ((Match.home_team_id == team.id) | (Match.away_team_id == team.id)),
            )
            .order_by(Match.date.desc())
            .all()
        )
        if window_size > 0:
            rows = rows[:window_size]

        for venue in ["all", "home", "away"]:
            venue_rows = rows
            if venue == "home":
                venue_rows = [r for r in rows if r[0].home_team_id == team.id]
            elif venue == "away":
                venue_rows = [r for r in rows if r[0].away_team_id == team.id]

            matches_count = len(venue_rows)
            if matches_count == 0:
                for market in MARKET_TO_COLUMNS.keys():
                    db.add(
                        TeamMarketAggregate(
                            league_id=league_id,
                            season=league.season,
                            team_id=team.id,
                            venue_type=venue,
                            market=market,
                            window_size=window_size,
                            avg_for=0.0,
                            avg_against=0.0,
                            matches_count=0,
                            updated_at=now,
                        )
                    )
                    written += 1
                continue

            # Goals are stored on Match while other markets come from MatchStatistics.
            goals_for = 0
            goals_against = 0
            for match, _stats in venue_rows:
                if match.home_team_id == team.id:
                    goals_for += match.home_goals or 0
                    goals_against += match.away_goals or 0
                else:
                    goals_for += match.away_goals or 0
                    goals_against += match.home_goals or 0

            db.add(
                TeamMarketAggregate(
                    league_id=league_id,
                    season=league.season,
                    team_id=team.id,
                    venue_type=venue,
                    market="goals",
                    window_size=window_size,
                    avg_for=round(goals_for / matches_count, 4),
                    avg_against=round(goals_against / matches_count, 4),
                    matches_count=matches_count,
                    updated_at=now,
                )
            )
            written += 1

            for market, (home_col, away_col) in MARKET_TO_COLUMNS.items():
                if market == "goals":
                    continue
                market_for = 0
                market_against = 0
                for match, stats in venue_rows:
                    home_val = getattr(stats, home_col) or 0
                    away_val = getattr(stats, away_col) or 0
                    if match.home_team_id == team.id:
                        market_for += home_val
                        market_against += away_val
                    else:
                        market_for += away_val
                        market_against += home_val
                db.add(
                    TeamMarketAggregate(
                        league_id=league_id,
                        season=league.season,
                        team_id=team.id,
                        venue_type=venue,
                        market=market,
                        window_size=window_size,
                        avg_for=round(market_for / matches_count, 4),
                        avg_against=round(market_against / matches_count, 4),
                        matches_count=matches_count,
                        updated_at=now,
                    )
                )
                written += 1

    db.flush()
    logger.info("Recomputed %d aggregate rows for league_id=%d", written, league_id)
    return written


def sync_upcoming_matches(db: Session, league_id: int, days: int = 7) -> int:
    """Sync upcoming matches from SStats into local DB."""
    league = db.query(League).get(league_id)
    if not league or not league.season_uid:
        return 0

    if _is_world_cup(league):
        days = 0

    run = _start_sync_run(db, source="sync_upcoming_matches", league=league)
    team_map = _build_team_map(db, league_id)
    existing_by_sstats_id = {
        m.sstats_id: m
        for m in db.query(Match).filter(
            Match.league_id == league_id,
            Match.sstats_id.isnot(None),
        ).all()
    }
    rows_written = 0

    try:
        games = fetch_all_games_by_season_uid_sync(
            season_uid=league.season_uid,
            ended=False,
            upcoming=True,
        )
        for game in games:
            sstats_gid = _safe_int(game.get("id"))
            if not sstats_gid:
                continue
            home_team = game.get("homeTeam") or {}
            away_team = game.get("awayTeam") or {}
            home_tid = team_map.get(_safe_int(home_team.get("id")))
            away_tid = team_map.get(_safe_int(away_team.get("id")))
            if not home_tid or not away_tid:
                continue

            match_date = None
            date_str = game.get("date")
            if date_str:
                try:
                    match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, TypeError):
                    pass
            if not match_date:
                continue

            if days > 0:
                max_dt = datetime.utcnow().replace(microsecond=0) + timedelta(days=days)
                if match_date > max_dt:
                    continue

            existing = existing_by_sstats_id.get(sstats_gid)
            if existing:
                existing.home_team_id = home_tid
                existing.away_team_id = away_tid
                existing.date = match_date
                existing.status = "NS"
                existing.round = game.get("roundName")
                rows_written += 1
                continue

            db.add(
                Match(
                    league_id=league_id,
                    season=league.season,
                    sstats_id=sstats_gid,
                    home_team_id=home_tid,
                    away_team_id=away_tid,
                    home_goals=None,
                    away_goals=None,
                    date=match_date,
                    status="NS",
                    round=game.get("roundName"),
                )
            )
            rows_written += 1

        _finish_sync_run(db, run, rows_written=rows_written)
        db.commit()
        return rows_written
    except Exception as exc:
        _finish_sync_run(db, run, rows_written=rows_written, error=str(exc))
        db.commit()
        raise


# ─── Utilities: refresh teams/logos ────────────────────────────────────────────


def refresh_team_logos(db: Session, league_id: int) -> int:
    """
    Re-fetch teams for a league from SStats standings + /Teams/{id}
    and update/create Team rows with correct logo_url.
    Returns number of teams processed.
    """
    league = db.query(League).get(league_id)
    if not league or not league.season_uid:
        logger.error("refresh_team_logos: league %d missing or has no season_uid", league_id)
        return 0

    before_count = db.query(Team).filter(Team.league_id == league_id).count()
    _seed_teams_from_standings(db, league, league.season_uid)
    if _is_world_cup(league) and db.query(Team).filter(Team.league_id == league_id).count() == before_count:
        _seed_teams_from_games(db, league)
    db.commit()
    after_count = db.query(Team).filter(Team.league_id == league_id).count()

    logger.info(
        "refresh_team_logos: league_id=%d teams_before=%d teams_after=%d",
        league_id,
        before_count,
        after_count,
    )
    return after_count


# ─── Full sync (seed + matches + standings) ────────────────────────────────────

def full_sync(
    db: Session,
    sstats_league_id: int = 39,
    year: Optional[int] = None,
    league_name_ru: Optional[str] = None,
    league_key: Optional[str] = None,
) -> bool:
    """
    Complete pipeline: seed league/teams → sync matches → sync standings.
    Returns True on success.
    """
    logger.info("=== Full sync starting: sstats_league=%d year=%s ===", sstats_league_id, year)

    league = seed_league(db, sstats_league_id, year, league_name_ru=league_name_ru, league_key=league_key)
    if not league:
        return False

    new_matches = sync_matches(db, league.id)
    logger.info("Synced %d new matches", new_matches)

    sync_standings(db, league.id)
    recompute_team_market_aggregates(db, league.id)
    db.commit()

    logger.info("=== Full sync complete for league_id=%d ===", league.id)
    return True
