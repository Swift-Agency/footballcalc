from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class LeagueMatcher:
    name_contains: tuple[str, ...]
    country_contains: Optional[str] = None
    # Substrings that disqualify a league (e.g. "2." filters out 2. Bundesliga).
    name_excludes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CuratedLeague:
    key: str
    name_ru: str
    matcher: LeagueMatcher


# Display order in league picker (matches Figma).
LEAGUE_DISPLAY_ORDER: tuple[str, ...] = (
    "world_cup",
    "ucl",
    "uel",
    "uecl",
    "epl",
    "laliga",
    "serie_a",
    "bundesliga",
    "ligue_1",
    "rpl",
)


def league_display_index(key: Optional[str]) -> int:
    if not key:
        return len(LEAGUE_DISPLAY_ORDER)
    try:
        return LEAGUE_DISPLAY_ORDER.index(key)
    except ValueError:
        return len(LEAGUE_DISPLAY_ORDER)


CURATED_LEAGUES: tuple[CuratedLeague, ...] = (
    CuratedLeague(
        key="world_cup",
        name_ru="Чемпионат мира",
        matcher=LeagueMatcher(
            name_contains=("world cup",),
            country_contains="world",
            name_excludes=(
                "women",
                "u-",
                "youth",
                "under",
                "club",
                "qualification",
                "kings",
                "play-in",
                "play-offs",
                "nations",
                "u17",
                "u20",
            ),
        ),
    ),
    CuratedLeague(
        key="ucl",
        name_ru="Лига чемпионов УЕФА",
        matcher=LeagueMatcher(name_contains=("uefa champions league",)),
    ),
    CuratedLeague(
        key="uel",
        name_ru="Лига Европы УЕФА",
        matcher=LeagueMatcher(name_contains=("uefa europa league",)),
    ),
    CuratedLeague(
        key="uecl",
        name_ru="Лига конференций УЕФА",
        matcher=LeagueMatcher(name_contains=("uefa europa conference league", "uefa conference league")),
    ),
    CuratedLeague(
        key="epl",
        name_ru="Английская Премьер-лига",
        matcher=LeagueMatcher(name_contains=("premier league",), country_contains="england"),
    ),
    CuratedLeague(
        key="laliga",
        name_ru="Ла Лига",
        matcher=LeagueMatcher(name_contains=("laliga", "la liga"), country_contains="spain"),
    ),
    CuratedLeague(
        key="serie_a",
        name_ru="Серия А",
        matcher=LeagueMatcher(name_contains=("serie a",), country_contains="italy"),
    ),
    CuratedLeague(
        key="bundesliga",
        name_ru="Бундеслига",
        matcher=LeagueMatcher(
            name_contains=("bundesliga",),
            country_contains="germany",
            # API lists "2. Bundesliga" before "Bundesliga"; both match name_contains otherwise.
            name_excludes=("2.",),
        ),
    ),
    CuratedLeague(
        key="ligue_1",
        name_ru="Лига 1",
        matcher=LeagueMatcher(name_contains=("ligue 1",), country_contains="france"),
    ),
    CuratedLeague(
        key="rpl",
        name_ru="Российская Премьер-лига",
        matcher=LeagueMatcher(name_contains=("premier league",), country_contains="russia"),
    ),
)


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _league_name(league: dict) -> str:
    return _normalize(str(league.get("name") or ""))


def _country_name(league: dict) -> str:
    country = league.get("country") or {}
    if isinstance(country, dict):
        return _normalize(str(country.get("name") or ""))
    return _normalize(str(country))


def _is_match(league: dict, curated: CuratedLeague) -> bool:
    name = _league_name(league)
    if not name:
        return False
    for ex in curated.matcher.name_excludes:
        if ex and ex in name:
            return False
    if not any(term in name for term in curated.matcher.name_contains):
        return False
    if curated.matcher.country_contains:
        return curated.matcher.country_contains in _country_name(league)
    return True


def resolve_curated_leagues(api_leagues: Iterable[dict]) -> tuple[list[tuple[CuratedLeague, dict]], list[str]]:
    """
    Resolve curated league definitions against /Leagues payload.
    Returns:
      - list of tuples (curated definition, matched api league dict)
      - list of unresolved curated keys
    """
    api_list = list(api_leagues)
    resolved: list[tuple[CuratedLeague, dict]] = []
    missing: list[str] = []

    for curated in CURATED_LEAGUES:
        match = next((league for league in api_list if _is_match(league, curated)), None)
        if not match:
            missing.append(curated.key)
            continue
        resolved.append((curated, match))
    return resolved, missing
