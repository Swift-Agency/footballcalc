from pydantic import BaseModel, model_validator
from typing import Optional, List

from app.services.logo_proxy import team_logo_proxy_url


class LeagueOut(BaseModel):
    id: int
    key: Optional[str] = None
    name: str
    name_en: str
    logo_url: Optional[str] = None
    logo_small_url: Optional[str] = None
    country: Optional[str] = None
    has_groups: bool = False
    season: Optional[int] = None
    sstats_id: Optional[int] = None
    is_locked: bool = False

    class Config:
        from_attributes = True


class TeamShort(BaseModel):
    id: int
    name: str
    name_en: str
    logo_url: Optional[str] = None
    league_id: Optional[int] = None

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def _rewrite_logo_url_to_proxy(self):
        self.logo_url = team_logo_proxy_url(self.id, self.logo_url)
        return self


class StandingRow(BaseModel):
    position: int
    team: TeamShort
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class StandingGroup(BaseModel):
    name: str
    rows: List[StandingRow]


class StandingsResponse(BaseModel):
    rows: Optional[List[StandingRow]] = None
    groups: Optional[List[StandingGroup]] = None


class AdvancedStatsRow(BaseModel):
    team: TeamShort
    matches: int
    srt: float
    srt1: float
    srt2: float
    obz_pct: float


class SmallMarketRow(BaseModel):
    team: TeamShort
    matches: int
    srt: float
    srt1: float
    srt2: float


class XgRow(BaseModel):
    team: TeamShort
    matches: int
    xg: float
    xga: float
    delta_g: float
    delta_ga: float


class MatchOut(BaseModel):
    id: int
    date: str
    time: str
    home_team: TeamShort
    away_team: TeamShort


class MatchTeamStats(BaseModel):
    position: int
    team: TeamShort
    srt: float
    srt1: float
    srt2: float
    obz_pct: float
    matches: int
    points: int


class MatchDetailOut(BaseModel):
    match: MatchOut
    general_stats: List[MatchTeamStats]
    by_position_stats: List[MatchTeamStats]


class CalculatorOddsRow(BaseModel):
    event: str
    subevent: Optional[str] = None
    probability: float
    odds: float


class CalculatorSection(BaseModel):
    id: str
    title: str
    rows: List[CalculatorOddsRow]


class CalculatorResult(BaseModel):
    home_team: TeamShort
    away_team: TeamShort
    main_outcomes: List[CalculatorOddsRow]
    sections: List[CalculatorSection]


class TeamProfileSummary(BaseModel):
    team: TeamShort
    matches: int
    srt: float
    srt1: float
    srt2: float
    obz_pct: float


class TeamSmallmarketMetric(BaseModel):
    metric: str
    label: str
    srt: float
    srt1: float
    srt2: float


class TeamProfileXg(BaseModel):
    team: TeamShort
    matches: int
    xg: float
    xga: float
    delta_g: float
    delta_ga: float


class TeamProfileResponse(BaseModel):
    team: TeamShort
    summary: TeamProfileSummary
    smallmarkets: List[TeamSmallmarketMetric]
    xg: Optional[TeamProfileXg] = None


# ─── Quota schemas ────────────────────────────────────────────────────────────

class UsageQuota(BaseModel):
    is_unlimited: bool
    weekly_limit: int
    used: int
    remaining: int
    resets_at: Optional[str] = None


# ─── Billing schemas ──────────────────────────────────────────────────────────

class BillingCheckoutRequest(BaseModel):
    return_url: Optional[str] = None
    plan_type: str = "monthly"          # monthly | world_cup
    referral_code: Optional[str] = None  # inviter's referral code (filled by frontend start_param)


class BillingCheckoutResponse(BaseModel):
    confirmation_url: str
    payment_id: int


class BillingPaymentStatus(BaseModel):
    payment_id: int
    status: str


class BillingMeResponse(BaseModel):
    is_subscribed: bool
    is_unlimited: bool = False
    plan_type: Optional[str] = None     # monthly | world_cup | None
    status: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    quota: Optional[UsageQuota] = None
    # Referral info
    referral_code: Optional[str] = None
    referral_link: Optional[str] = None
    has_discount: bool = False
    discount_expires_at: Optional[str] = None


class ReferralClaimRequest(BaseModel):
    referral_code: str
