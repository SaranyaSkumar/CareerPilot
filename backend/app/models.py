import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Index, Numeric, String, Text, Uuid, func, text
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
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="New Zealand")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    source: Mapped[str] = mapped_column(String(120), default="Manually added")
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
