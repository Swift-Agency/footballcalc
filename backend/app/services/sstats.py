"""
SStats.net API client.
Base URL: https://api.sstats.net

Provides typed fetchers for:
  /Leagues              – all leagues with season list
  /Seasons/standings    – standings by season uid
  /Games/list           – match list (paginated)
  /Games/{id}           – single match with full statistics
  /Teams/list           – team search (logos, metadata)
"""
import os
import time
import logging
import httpx
from typing import Optional, List, Any

from app.services import external_metrics
from app.services.effective_keys import get_sstats_api_key
from app.services import sstats_cache
from app.services.settings_reader import get_cache_options

logger = logging.getLogger("sstats")

SSTATS_BASE = os.getenv("SSTATS_API_URL", "https://api.sstats.net").rstrip("/")
TIMEOUT = 30
MAX_RETRIES = 3

_last_request_ts: float = 0.0


def _rate_limit_delay() -> float:
    return 0.5 if get_sstats_api_key() else 2.0


def _params(**extra: Any) -> dict:
    p = {k: v for k, v in extra.items() if v is not None}
    key = get_sstats_api_key()
    if key:
        p["apikey"] = key
    return p


def _throttle():
    """Enforce minimum delay between requests to respect rate limits."""
    global _last_request_ts
    delay = _rate_limit_delay()
    elapsed = time.time() - _last_request_ts
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_request_ts = time.time()


def _scope_for_path(path: str) -> str:
    if path == "/Leagues":
        return "leagues"
    if path == "/Seasons/standings":
        return "standings"
    if path == "/Games/list":
        return "games_list"
    if "/glicko/" in path:
        return "game_glicko"
    if path.startswith("/Games/"):
        return "game_detail"
    if path.startswith("/Teams"):
        return "teams"
    return "other"


def _get_sync(path: str, throttle: bool = False, **kwargs) -> Optional[dict]:
    url = f"{SSTATS_BASE}{path}"
    params = _params(**kwargs)
    ttl, cache_on = get_cache_options()
    scope = _scope_for_path(path)
    cache_key_str = sstats_cache.cache_key(path, params)

    if cache_on and scope != "other":
        cached = sstats_cache.get_cached(scope, cache_key_str, ttl)
        if cached is not None:
            return cached

    for attempt in range(1, MAX_RETRIES + 1):
        if throttle:
            _throttle()
        t0 = time.time()
        status_code: int | None = None
        err_msg: str | None = None
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = client.get(url, params=params)
                status_code = resp.status_code
                latency_ms = (time.time() - t0) * 1000
                external_metrics.record_sstats(status_code, latency_ms)
                if resp.status_code == 429:
                    wait = _rate_limit_delay() * attempt * 2
                    logger.warning("429 on %s, retry %d/%d in %.1fs", path, attempt, MAX_RETRIES, wait)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.warning("GET %s → %d", url, resp.status_code)
                    return None
                data = resp.json()
                if cache_on and scope != "other":
                    sstats_cache.set_cached(scope, cache_key_str, ttl, data)
                return data
        except Exception as exc:
            latency_ms = (time.time() - t0) * 1000
            err_msg = str(exc)
            external_metrics.record_sstats(None, latency_ms, err_msg)
            logger.error("GET %s failed (attempt %d): %s", url, attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(_rate_limit_delay() * attempt)
    return None


# ─── Leagues ──────────────────────────────────────────────────────────────────

def fetch_leagues_sync() -> List[dict]:
    """GET /Leagues → list of leagues with seasons."""
    body = _get_sync("/Leagues")
    if not body:
        return []
    return body.get("data") or []


def find_league(leagues: List[dict], sstats_id: int) -> Optional[dict]:
    for lg in leagues:
        if lg.get("id") == sstats_id:
            return lg
    return None


def find_current_season(league: dict, year: Optional[int] = None) -> Optional[dict]:
    """Return the season dict for a given year (or the latest if year is None)."""
    seasons = league.get("seasons") or []
    if not seasons:
        return None
    if year is not None:
        for s in seasons:
            if s.get("year") == year:
                return s
        return None
    return max(seasons, key=lambda s: s.get("year", 0))


# ─── Standings ────────────────────────────────────────────────────────────────

def fetch_standings_sync(season_uid: str) -> Optional[dict]:
    """GET /Seasons/standings?uid=... → standings data."""
    body = _get_sync("/Seasons/standings", uid=season_uid)
    if not body:
        return None
    return body.get("data")


# ─── Games ────────────────────────────────────────────────────────────────────

def fetch_games_sync(
    league_id: int,
    year: int,
    ended: bool = True,
    offset: int = 0,
    limit: int = 1000,
) -> List[dict]:
    """GET /Games/list by league+year → paginated game list (short form)."""
    body = _get_sync(
        "/Games/list",
        leagueid=league_id,
        year=year,
        ended=ended,
        offset=offset,
        limit=limit,
        order=1,
    )
    if not body:
        return []
    return body.get("data") or []


def fetch_games_by_season_uid_sync(
    season_uid: str,
    ended: Optional[bool] = None,
    upcoming: Optional[bool] = None,
    offset: int = 0,
    limit: int = 1000,
) -> List[dict]:
    """GET /Games/list by seasonUid (supports ended/upcoming)."""
    body = _get_sync(
        "/Games/list",
        seasonUid=season_uid,
        ended=ended,
        upcoming=upcoming,
        offset=offset,
        limit=limit,
        order=1,
    )
    if not body:
        return []
    return body.get("data") or []


def fetch_games_by_league_interval_sync(
    league_id: int,
    from_date: str,
    to_date: str,
    offset: int = 0,
    limit: int = 1000,
) -> List[dict]:
    """GET /Games/list by leagueid + date interval."""
    params = {
        "leagueid": league_id,
        "from": from_date,
        "to": to_date,
        "offset": offset,
        "limit": limit,
        "order": 1,
    }
    body = _get_sync("/Games/list", **params)
    if not body:
        return []
    return body.get("data") or []


def fetch_all_games_sync(league_id: int, year: int) -> List[dict]:
    """Fetch all ended games for a league+year, handling pagination."""
    all_games: List[dict] = []
    offset = 0
    while True:
        batch = fetch_games_sync(league_id, year, ended=True, offset=offset, limit=1000)
        if not batch:
            break
        all_games.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    logger.info("Fetched %d total games for league=%d year=%d", len(all_games), league_id, year)
    return all_games


def fetch_all_games_by_season_uid_sync(
    season_uid: str,
    ended: Optional[bool] = None,
    upcoming: Optional[bool] = None,
) -> List[dict]:
    """Fetch all games by season UID with pagination."""
    all_games: List[dict] = []
    offset = 0
    while True:
        batch = fetch_games_by_season_uid_sync(
            season_uid=season_uid,
            ended=ended,
            upcoming=upcoming,
            offset=offset,
            limit=1000,
        )
        if not batch:
            break
        all_games.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    logger.info(
        "Fetched %d total games for seasonUid=%s ended=%s upcoming=%s",
        len(all_games),
        season_uid,
        ended,
        upcoming,
    )
    return all_games


def fetch_game_detail_sync(game_id: int) -> Optional[dict]:
    """GET /Games/{id} → full game data with statistics + expectedGoals. Throttled."""
    body = _get_sync(f"/Games/{game_id}", throttle=True)
    if not body:
        return None
    return body.get("data")


def fetch_game_glicko_sync(game_id: int) -> Optional[dict]:
    """GET /Games/glicko/{id} → fixture + homeXg, awayXg. Lighter than full detail. Throttled."""
    body = _get_sync(f"/Games/glicko/{game_id}", throttle=True)
    if not body:
        return None
    return body.get("data")


# ─── Teams ────────────────────────────────────────────────────────────────────

def fetch_teams_sync(
    name: Optional[str] = None,
    country: Optional[str] = None,
    offset: int = 0,
    limit: int = 100,
) -> List[dict]:
    """GET /Teams/list → team list with logos."""
    body = _get_sync(
        "/Teams/list",
        Name=name if name and len(name) >= 2 else None,
        Country=country,
        Offset=offset,
        Limit=limit,
    )
    if not body:
        return []
    return body.get("data") or []


def fetch_team_by_id(team_id: int) -> Optional[dict]:
    """GET /Teams/{id} → single team detail. Throttled."""
    body = _get_sync(f"/Teams/{team_id}", throttle=True)
    if not body:
        return None
    return body.get("data")


