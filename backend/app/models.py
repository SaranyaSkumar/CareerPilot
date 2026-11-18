import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CareerProfile(Base):
    __tablename__ = "career_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    headline: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="New Zealand")
    phone: Mapped[str] = mapped_column(String(40), default="")
    website_url: Mapped[str] = mapped_column(String(500), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    github_url: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[str] = mapped_column(Text, default="")


class CvDocument(Base):
    __tablename__ = "cv_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    headline: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    experience: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[str] = mapped_column(Text, default="")
    education: Mapped[str] = mapped_column(Text, default="")


class CvVersion(Base):
    __tablename__ = "cv_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    job_title: Mapped[str] = mapped_column(String(200), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CareerTrackProfile(Base):
    __tablename__ = "career_track_profiles"
    __table_args__ = (Index("career_track_profiles_user_updated_idx", "user_id", "updated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(20), default="full_time", nullable=False)
    target_roles: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="New Zealand", nullable=False)
    cv_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    headline: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    experience: Mapped[str] = mapped_column(Text, default="", nullable=False)
    skills: Mapped[str] = mapped_column(Text, default="", nullable=False)
    education: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CvVariant(Base):
    """A named CV kept beside the original draft.

    Tailoring saves here so the master cv_documents row is left unchanged.
    One variant per user may be marked the default.
    """

    __tablename__ = "cv_variants"
    __table_args__ = (
        Index("cv_variants_user_created_idx", "user_id", "created_at"),
        Index(
            "cv_variants_one_default_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    job_title: Mapped[str] = mapped_column(String(200), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    job_id: Mapped[int | None] = mapped_column(nullable=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("career_track_profiles.id", ondelete="SET NULL"), nullable=True)
    job_description: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[str] = mapped_column(String(160), default="")
    headline: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    experience: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[str] = mapped_column(Text, default="")
    education: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JobListing(Base):
    __tablename__ = "job_listings"
    __table_args__ = (
        Index(
            "job_listings_user_url_unique",
            "user_id",
            "url",
            unique=True,
            sqlite_where=text("url <> ''"),
            postgresql_where=text("url <> ''"),
        ),
        Index(
            "job_listings_user_dedupe_unique",
            "user_id",
            "dedupe_key",
            unique=True,
            sqlite_where=text("dedupe_key <> ''"),
            postgresql_where=text("dedupe_key <> ''"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="New Zealand")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    source: Mapped[str] = mapped_column(String(120), default="Manually added")
    salary: Mapped[str] = mapped_column(String(200), default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(20), default="saved", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AiUsageEvent(Base):
    """One Anthropic call, reserved before the request and completed with actual tokens.

    Rows are the source of truth for the per-user daily cap and the app-wide
    monthly cap. CV text is never stored here.
    """

    __tablename__ = "ai_usage_events"
    __table_args__ = (
        Index("ai_usage_events_user_created_idx", "user_id", "created_at"),
        Index("ai_usage_events_created_idx", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="reserved")
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JobDiscoverySettings(Base):
    """One search profile per user for automatic job discovery."""

    __tablename__ = "job_discovery_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    country: Mapped[str] = mapped_column(String(2), default="nz", nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="New Zealand", nullable=False)
    keywords: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    remote_preference: Mapped[str] = mapped_column(String(20), default="any", nullable=False)
    query_fingerprint: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    last_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JobProviderSetting(Base):
    """Whether this user has turned one job provider on or off."""

    __tablename__ = "job_provider_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "provider_key", name="job_provider_settings_user_provider_unique"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JobProviderCache(Base):
    """Shared cache of public provider listings. It stores no user content."""

    __tablename__ = "job_provider_cache"
    __table_args__ = (
        UniqueConstraint(
            "provider_key",
            "query_fingerprint",
            name="job_provider_cache_query_unique",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    query_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[list] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JobProviderQuota(Base):
    """Daily call counter for an app-level provider key. It stores no user content."""

    __tablename__ = "job_provider_quota"
    __table_args__ = (
        UniqueConstraint("provider_key", "quota_day", name="job_provider_quota_day_unique"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    quota_day: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(nullable=False, default=0)


class JobApplication(Base):
    """A user's tracked opportunity and application progress."""

    __tablename__ = "job_applications"
    __table_args__ = (
        Index("job_applications_user_updated_idx", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="New Zealand", nullable=False)
    url: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    stage: Mapped[str] = mapped_column(String(32), default="interested", nullable=False, index=True)
    applied_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_action: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cv_version_id: Mapped[int | None] = mapped_column(ForeignKey("cv_versions.id", ondelete="SET NULL"), nullable=True)
    cover_letter: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
