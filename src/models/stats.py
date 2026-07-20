import uuid
from datetime import datetime

from sqlalchemy import Integer, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class Stats(Base):
    __tablename__ = "stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    total_active_jobs: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    total_companies: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    total_cities: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    jobs_added_last_24h: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    jobs_closed_last_24h: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    last_full_poll_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    avg_poll_duration_ms: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
