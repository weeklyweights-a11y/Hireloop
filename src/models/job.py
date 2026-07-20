import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class Job(Base):
    __tablename__ = "jobs"
    # Identity is company + the id its ATS assigned. Two different companies on the
    # same ATS (e.g. many "custom" tenants) legitimately reuse the same job id, so
    # the unique key must be per-company — this is also the differ's lookup key.
    __table_args__ = (UniqueConstraint("source_company_slug", "source_job_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_company_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    source_ats: Mapped[str] = mapped_column(String(50), nullable=False)
    source_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    apply_url: Mapped[str | None] = mapped_column(String(1000))
    title_raw: Mapped[str] = mapped_column(String(500), nullable=False)
    title_normalized: Mapped[str | None] = mapped_column(String(255))
    title_metadata: Mapped[dict | None] = mapped_column(JSONB)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_logo_url: Mapped[str | None] = mapped_column(String(500))
    department: Mapped[str | None] = mapped_column(String(255))
    location_city: Mapped[str | None] = mapped_column(String(100))
    location_state: Mapped[str | None] = mapped_column(String(50))
    location_country: Mapped[str | None] = mapped_column(String(10), server_default=text("'US'"))
    location_metro: Mapped[str | None] = mapped_column(String(100))
    remote_policy: Mapped[str | None] = mapped_column(String(20), server_default=text("'unknown'"))
    seniority: Mapped[str | None] = mapped_column(String(20))
    employment_type: Mapped[str | None] = mapped_column(
        String(20), server_default=text("'full_time'")
    )
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(10), server_default=text("'USD'"))
    salary_period: Mapped[str | None] = mapped_column(String(20), server_default=text("'annual'"))
    experience_min: Mapped[int | None] = mapped_column(Integer)
    experience_max: Mapped[int | None] = mapped_column(Integer)
    skills_required: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'"))
    skills_nice_to_have: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'"))
    skills_implied: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'"))
    visa_sponsorship: Mapped[str | None] = mapped_column(
        String(20), server_default=text("'unknown'")
    )
    description_text: Mapped[str | None] = mapped_column(Text)
    description_html: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(20), server_default=text("'active'"))
    consecutive_misses: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    first_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
