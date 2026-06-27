"""
Data-source metadata ORM model: DataSourceLog.

Tracks external data fetches for audit and observability.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DataSourceLog(Base):
    """Audit log for external data-source fetch operations."""

    __tablename__ = "data_source_logs"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    source_name: Mapped[str | None] = mapped_column(
        String(50), default=None, comment="Name of the data source"
    )
    fetch_type: Mapped[str | None] = mapped_column(
        String(50), default=None, comment="Type of fetch (e.g. daily_nav, holdings)"
    )
    status: Mapped[str | None] = mapped_column(
        String(20), default=None, comment="Fetch status (success, failed, partial)"
    )
    record_count: Mapped[int | None] = mapped_column(
        Integer, default=None, comment="Number of records fetched"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, default=None, comment="Error message if fetch failed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Fetch operation timestamp",
    )
