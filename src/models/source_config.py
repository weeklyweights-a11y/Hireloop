import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class JobSourceConfig(Base):
    __tablename__ = "job_source_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    company_logo_url: Mapped[str | None] = mapped_column(String(500))
    company_website: Mapped[str | None] = mapped_column(String(500))
    ats_type: Mapped[str] = mapped_column(String(50), nullable=False)
    api_endpoint: Mapped[str] = mapped_column(String(1000), nullable=False)
    api_method: Mapped[str | None] = mapped_column(String(10), server_default=text("'GET'"))
    api_headers: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'"))
    api_params: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'"))
    api_body: Mapped[dict | None] = mapped_column(JSONB)
    response_path: Mapped[str | None] = mapped_column(String(255))
    field_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pagination_config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'"))
    polling_interval_hours: Mapped[int | None] = mapped_column(Integer, server_default=text("2"))
    active: Mapped[bool | None] = mapped_column(Boolean, server_default=text("TRUE"))
    last_polled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    total_jobs_found: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
