"""Database models for the application."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AdBucket(str, PyEnum):
    """Ad performance bucket classification."""

    BEST = "best"
    WORST = "worst"
    UNKNOWN = "unknown"


class SyncStatus(str, PyEnum):
    """Sync job status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class User(Base):
    """User model - single-tenant for MVP, multi-tenant ready."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    connected_accounts: Mapped[list["ConnectedAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ConnectedAccount(Base):
    """Google Ads connected account."""

    __tablename__ = "connected_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(20), index=True)
    login_customer_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    descriptive_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    time_zone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Encrypted OAuth tokens (stored as base64-encoded encrypted strings)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    encrypted_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Sync metadata
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sync_status: Mapped[Optional[str]] = mapped_column(
        Enum(SyncStatus), nullable=True, default=SyncStatus.PENDING
    )
    last_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="connected_accounts")
    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    sync_runs: Mapped[list["SyncRun"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "customer_id", name="uq_user_customer"),
        Index("ix_connected_accounts_user_customer", "user_id", "customer_id"),
    )


class SyncRun(Base):
    """Sync job execution tracking."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("connected_accounts.id"), index=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(SyncStatus), default=SyncStatus.PENDING, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ads_synced: Mapped[int] = mapped_column(Integer, default=0)
    campaigns_synced: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    account: Mapped["ConnectedAccount"] = relationship(back_populates="sync_runs")


class Campaign(Base):
    """Google Ads campaign."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("connected_accounts.id"), index=True)
    campaign_id: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    advertising_channel_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    account: Mapped["ConnectedAccount"] = relationship(back_populates="campaigns")
    ad_groups: Mapped[list["AdGroup"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("account_id", "campaign_id", name="uq_account_campaign"),
        Index("ix_campaigns_account_campaign", "account_id", "campaign_id"),
    )


class AdGroup(Base):
    """Google Ads ad group."""

    __tablename__ = "ad_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    ad_group_id: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(back_populates="ad_groups")
    ads: Mapped[list["Ad"]] = relationship(back_populates="ad_group", cascade="all, delete-orphan")
    keywords: Mapped[list["Keyword"]] = relationship(
        back_populates="ad_group", cascade="all, delete-orphan"
    )


class Ad(Base):
    """Google Ads ad (RSA focus)."""

    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ad_group_id: Mapped[int] = mapped_column(ForeignKey("ad_groups.id"), index=True)
    ad_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    ad_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))

    # Ad content (JSON for flexibility with different ad types)
    headlines: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    descriptions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    final_urls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Raw API response snapshot for provenance
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Ad creation timestamp from Google Ads API
    google_ads_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Performance bucket
    bucket: Mapped[Optional[str]] = mapped_column(
        Enum(AdBucket), nullable=True, default=AdBucket.UNKNOWN, index=True
    )
    bucket_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bucket_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    ad_group: Mapped["AdGroup"] = relationship(back_populates="ads")
    metrics_daily: Mapped[list["AdMetricsDaily"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    metrics_90d: Mapped[Optional["AdMetrics90d"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan", uselist=False
    )
    suggestions: Mapped[list["Suggestion"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )


class AdMetricsDaily(Base):
    """Daily ad metrics."""

    __tablename__ = "ad_metrics_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id"), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Core metrics
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    conversions: Mapped[float] = mapped_column(Float, default=0.0)
    all_conversions: Mapped[float] = mapped_column(Float, default=0.0)

    # Computed metrics (stored for performance)
    ctr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_per_conversion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="metrics_daily")

    __table_args__ = (
        UniqueConstraint("ad_id", "date", name="uq_ad_date"),
        Index("ix_ad_metrics_daily_ad_date", "ad_id", "date"),
    )


class AdMetrics90d(Base):
    """90-day aggregate ad metrics."""

    __tablename__ = "ad_metrics_90d"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id"), unique=True, index=True)

    # Aggregate metrics
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    conversions: Mapped[float] = mapped_column(Float, default=0.0)
    all_conversions: Mapped[float] = mapped_column(Float, default=0.0)

    # Computed metrics
    ctr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_per_conversion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Date range
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="metrics_90d")


class Keyword(Base):
    """Ad group keywords (best-effort from ad_group_criterion)."""

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ad_group_id: Mapped[int] = mapped_column(ForeignKey("ad_groups.id"), index=True)
    criterion_id: Mapped[str] = mapped_column(String(50), index=True)
    text: Mapped[str] = mapped_column(String(255))
    match_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Quality score metrics (stored as JSON for flexibility)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    ad_group: Mapped["AdGroup"] = relationship(back_populates="keywords")

    __table_args__ = (
        UniqueConstraint("ad_group_id", "criterion_id", name="uq_adgroup_criterion"),
    )


class Suggestion(Base):
    """Generated ad copy suggestions."""

    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id"), index=True)
    suggestion_run_id: Mapped[int] = mapped_column(ForeignKey("suggestion_runs.id"), index=True)

    # Generated content
    headlines: Mapped[dict] = mapped_column(JSON)
    descriptions: Mapped[dict] = mapped_column(JSON)

    # Provenance
    prompt_version: Mapped[str] = mapped_column(String(50))
    exemplar_ad_ids: Mapped[list] = mapped_column(JSON)
    similarity_scores: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    model_used: Mapped[str] = mapped_column(String(100))

    # Application status
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_ad_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="suggestions")
    suggestion_run: Mapped["SuggestionRun"] = relationship(back_populates="suggestions")


class SuggestionRun(Base):
    """Batch suggestion generation run."""

    __tablename__ = "suggestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("connected_accounts.id"), index=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    ads_processed: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_generated: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    suggestions: Mapped[list["Suggestion"]] = relationship(
        back_populates="suggestion_run", cascade="all, delete-orphan"
    )
