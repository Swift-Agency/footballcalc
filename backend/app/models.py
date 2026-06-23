from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index, BigInteger, Text, Numeric
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

# World Cup 2026 final date (end of last match day, UTC)
WORLD_CUP_ENDS_AT = datetime(2026, 7, 19, 23, 59, 59)
WEEKLY_FREE_QUOTA = 5


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    api_football_id = Column(Integer, unique=True)
    sstats_id = Column(Integer)
    logo_url = Column(String)
    logo_small_url = Column(String)
    country = Column(String)
    has_groups = Column(Boolean, default=False)
    season = Column(Integer)
    season_uid = Column(String)

    teams = relationship("Team", back_populates="league")
    standings = relationship("Standing", back_populates="league")
    matches = relationship("Match", back_populates="league")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        Index("ix_teams_league_sstats_unique", "league_id", "sstats_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    api_football_id = Column(Integer)
    sstats_id = Column(Integer)
    sstats_name = Column(String)
    logo_url = Column(String)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)

    league = relationship("League", back_populates="teams")
    standings = relationship("Standing", back_populates="team")


class Standing(Base):
    __tablename__ = "standings"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season = Column(Integer, nullable=False)
    venue_type = Column(String, nullable=False, default="all")
    group_name = Column(String, nullable=True)
    position = Column(Integer)
    played = Column(Integer, default=0)
    won = Column(Integer, default=0)
    drawn = Column(Integer, default=0)
    lost = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    goal_difference = Column(Integer, default=0)
    points = Column(Integer, default=0)

    team = relationship("Team", back_populates="standings")
    league = relationship("League", back_populates="standings")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_league_season_status_date", "league_id", "season", "status", "date"),
        Index("ix_matches_home_away_date", "home_team_id", "away_team_id", "date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season = Column(Integer, nullable=False)
    api_football_id = Column(Integer, unique=True, nullable=True)
    sstats_id = Column(Integer, unique=True, nullable=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    home_goals = Column(Integer)
    away_goals = Column(Integer)
    date = Column(DateTime)
    status = Column(String, default="FT")
    round = Column(String)

    league = relationship("League", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    statistics = relationship("MatchStatistics", back_populates="match", uselist=False)
    xg = relationship("MatchXG", back_populates="match", uselist=False)


class MatchStatistics(Base):
    __tablename__ = "match_statistics"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, unique=True)
    home_yellow_cards = Column(Integer, default=0)
    away_yellow_cards = Column(Integer, default=0)
    home_corners = Column(Integer, default=0)
    away_corners = Column(Integer, default=0)
    home_shots_on_target = Column(Integer, default=0)
    away_shots_on_target = Column(Integer, default=0)
    home_shots_total = Column(Integer, default=0)
    away_shots_total = Column(Integer, default=0)
    home_fouls = Column(Integer, default=0)
    away_fouls = Column(Integer, default=0)
    home_offsides = Column(Integer, default=0)
    away_offsides = Column(Integer, default=0)

    match = relationship("Match", back_populates="statistics")


class MatchXG(Base):
    __tablename__ = "match_xg"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, unique=True)
    home_xg = Column(Float, default=0.0)
    away_xg = Column(Float, default=0.0)

    match = relationship("Match", back_populates="xg")


class TeamMarketAggregate(Base):
    __tablename__ = "team_market_aggregates"
    __table_args__ = (
        Index(
            "ix_team_market_aggregates_lookup",
            "league_id",
            "season",
            "team_id",
            "venue_type",
            "market",
            "window_size",
            unique=True,
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season = Column(Integer, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    venue_type = Column(String, nullable=False, default="all")
    market = Column(String, nullable=False)
    window_size = Column(Integer, nullable=False, default=0)
    avg_for = Column(Float, nullable=False, default=0.0)
    avg_against = Column(Float, nullable=False, default=0.0)
    matches_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False)

    league = relationship("League")
    team = relationship("Team")


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        Index("ix_sync_runs_league_season_started", "league_id", "season", "started_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    season = Column(Integer, nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)
    status = Column(String, nullable=False, default="running")
    error = Column(String)
    rows_written = Column(Integer, nullable=False, default=0)

    league = relationship("League")


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (Index("ix_admin_audit_created", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    action = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class RuntimeSecret(Base):
    """Optional DB override for SStats API key (encrypted with Fernet). Name: sstats_api_key."""

    __tablename__ = "runtime_secrets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    value_encrypted = Column(Text, nullable=False)


class AppSettings(Base):
    """Singleton row id=1: cache TTLs, feature flags, rate limit."""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    cache_ttl_seconds = Column(Integer, nullable=False, default=300)
    sstats_cache_enabled = Column(Boolean, nullable=False, default=True)
    feature_flags_json = Column(Text, nullable=False, default="{}")
    rate_limit_per_minute = Column(Integer, nullable=False, default=0)
    notifications_enabled = Column(Boolean, nullable=False, default=True)
    # Subscription settings (kept for compat but free_league_keys no longer gates access)
    free_league_keys_csv = Column(String, nullable=False, default="world_cup,ucl")
    subscription_price_rub = Column(Numeric(10, 2), nullable=False, default=480.00)
    subscription_period_days = Column(Integer, nullable=False, default=30)
    recurring_retry_days = Column(Integer, nullable=False, default=3)
    # Premium feature quota
    weekly_free_quota = Column(Integer, nullable=False, default=5)


class AppEvent(Base):
    __tablename__ = "app_events"
    __table_args__ = (Index("ix_app_events_type_created", "event_type", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)
    payload_json = Column(Text, nullable=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, nullable=False)


class NotificationDedup(Base):
    """Last sent notification per key to avoid spam."""

    __tablename__ = "notification_dedup"

    key = Column(String, primary_key=True)
    last_sent_at = Column(DateTime, nullable=False)


class TelegramUserPing(Base):
    """Unique Telegram users who reported via /api/events ping."""

    __tablename__ = "telegram_user_pings"

    telegram_user_id = Column(BigInteger, primary_key=True)
    first_seen_at = Column(DateTime, nullable=False)


class User(Base):
    """Telegram Mini App user. Created on first billing/premium interaction."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Referral system
    referral_code = Column(String, unique=True, nullable=True, index=True)
    referred_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    discount_expires_at = Column(DateTime, nullable=True)  # 24h from created_at if referred
    referral_bonus_granted_at = Column(DateTime, nullable=True)  # when inviter got their bonus

    subscription = relationship("Subscription", back_populates="user", uselist=False)
    payments = relationship(
        "Payment",
        back_populates="user",
        foreign_keys="Payment.user_id",
    )
    referred_by = relationship("User", foreign_keys=[referred_by_user_id], remote_side="User.id")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_yookassa_id", "yookassa_payment_id", unique=True),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True, index=True)
    yookassa_payment_id = Column(String, unique=True, index=True, nullable=False)
    kind = Column(String, nullable=False)          # initial | recurring | referral_bonus
    status = Column(String, nullable=False)        # pending | succeeded | canceled | failed
    amount_value = Column(Numeric(10, 2), nullable=False)
    amount_currency = Column(String, nullable=False, default="RUB")
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    # Plan & referral metadata
    plan_type = Column(String, nullable=True)       # monthly | world_cup
    discount_percent = Column(Integer, nullable=False, default=0)
    referral_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # referrer user

    user = relationship("User", back_populates="payments", foreign_keys=[user_id])
    subscription = relationship("Subscription", foreign_keys=[subscription_id])


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    status = Column(String, nullable=False)          # active | pending | past_due | canceled | expired
    starts_at = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, index=True, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    yookassa_payment_method_id = Column(String, nullable=True)
    last_payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    next_charge_at = Column(DateTime, nullable=True, index=True)
    canceled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # Plan type: monthly (auto-renews) or world_cup (fixed until Jul 19 2026)
    plan_type = Column(String, nullable=False, default="monthly")
    # Source: paid | referral_bonus
    source = Column(String, nullable=False, default="paid")

    user = relationship("User", back_populates="subscription")


class PremiumUsageEvent(Base):
    """Records each time a user consumes a premium feature (xG or calculator)."""

    __tablename__ = "premium_usage_events"
    __table_args__ = (
        Index("ix_premium_usage_user_week", "user_id", "week_start"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feature = Column(String, nullable=False)        # xg | calculator
    week_start = Column(DateTime, nullable=False)   # UTC Monday 00:00:00 of the current week
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (
        Index("ix_admin_users_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_superadmin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by_telegram_id = Column(BigInteger, nullable=True)


class LegalDocumentVersion(Base):
    __tablename__ = "legal_document_versions"
    __table_args__ = (
        Index("ix_legal_document_versions_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, unique=True, nullable=False)
    terms_url = Column(String, nullable=False)
    privacy_url = Column(String, nullable=False)
    disclaimer_url = Column(String, nullable=False)
    effective_at_msk = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by_telegram_id = Column(BigInteger, nullable=True)


class LegalAcceptance(Base):
    __tablename__ = "legal_acceptances"
    __table_args__ = (
        Index("ix_legal_acceptances_tg_accepted", "telegram_id", "accepted_at_msk"),
        Index("ix_legal_acceptances_doc_version", "document_version_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    accepted_at_msk = Column(DateTime, nullable=False)
    document_version_id = Column(Integer, ForeignKey("legal_document_versions.id"), nullable=False)
    document_version = Column(String, nullable=False)
    terms_url_snapshot = Column(String, nullable=False)
    privacy_url_snapshot = Column(String, nullable=False)
    disclaimer_url_snapshot = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    legal_document = relationship("LegalDocumentVersion")


class DeletedUserBlock(Base):
    __tablename__ = "deleted_user_blocks"
    __table_args__ = (
        Index("ix_deleted_user_blocks_tg_deleted", "telegram_id", "deleted_at_msk"),
    )

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    deleted_at_msk = Column(DateTime, nullable=False)
    reason = Column(String, nullable=True)
