"""
Fund-related ORM models: Fund, FundNav, FundHolding, FundManager.

All models include a nullable user_id column for future multi-tenancy.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Fund(Base):
    """Mutual fund or ETF product."""

    __tablename__ = "funds"

    code: Mapped[str] = mapped_column(
        String(10), primary_key=True, comment="Fund ticker code"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Fund display name"
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Fund type (e.g. stock, bond, hybrid)"
    )
    scale: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), default=None, comment="Fund AUM / scale in CNY"
    )
    fee_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), default=None, comment="Management fee rate (e.g. 0.0150)"
    )
    company: Mapped[str | None] = mapped_column(
        String(100), default=None, comment="Fund management company"
    )
    inception_date: Mapped[date | None] = mapped_column(
        Date, default=None, comment="Fund inception date"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, default=None, nullable=True, comment="Owner user ID"
    )


class FundNav(Base):
    """Daily net asset value (NAV) snapshot for a fund."""

    __tablename__ = "fund_navs"
    __table_args__ = (
        UniqueConstraint("fund_code", "date", name="uq_fund_nav_code_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    fund_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("funds.code", ondelete="CASCADE"),
        nullable=False,
        comment="FK to funds.code",
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="NAV valuation date"
    )
    nav: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, comment="Unit NAV"
    )
    accumulated_nav: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), default=None, comment="Accumulated NAV (includes dividends)"
    )
    daily_return: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), default=None, comment="Daily return (decimal, e.g. 0.0012)"
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, default=None, nullable=True, comment="Owner user ID"
    )


class FundHolding(Base):
    """Top holdings disclosure for a fund (quarterly/semi-annual reports)."""

    __tablename__ = "fund_holdings"
    __table_args__ = (
        UniqueConstraint(
            "fund_code", "report_date", "stock_code",
            name="uq_fund_holding_code_date_stock",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    fund_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("funds.code", ondelete="CASCADE"),
        nullable=False,
        comment="FK to funds.code",
    )
    report_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Report date (quarter-end)"
    )
    stock_code: Mapped[str | None] = mapped_column(
        String(10), default=None, comment="Stock / asset code"
    )
    stock_name: Mapped[str | None] = mapped_column(
        String(100), default=None, comment="Stock / asset name"
    )
    ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), default=None, comment="Weight in portfolio (decimal)"
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, default=None, nullable=True, comment="Owner user ID"
    )


class FundManager(Base):
    """Fund manager information."""

    __tablename__ = "fund_managers"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    fund_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("funds.code", ondelete="CASCADE"),
        nullable=False,
        comment="FK to funds.code",
    )
    name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Manager name"
    )
    start_date: Mapped[date | None] = mapped_column(
        Date, default=None, comment="Start date managing this fund"
    )
    tenure_return: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), default=None, comment="Return during tenure"
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, default=None, nullable=True, comment="Owner user ID"
    )
