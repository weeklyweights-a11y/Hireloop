import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class PollLog(Base):
    __tablename__ = "poll_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_source_configs.id")
    )
    company_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    jobs_found: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    jobs_new: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    jobs_updated: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    jobs_closed: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    polled_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
