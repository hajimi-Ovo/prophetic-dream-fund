"""
Portfolio-holding ORM models: Holding, FundTransaction, FundWatchlist.

These models track the user's actual fund positions and watch list.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Holding(Base):
    """A user's position (holding) in a particular fund."""

    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    fund_code: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="Fund ticker code"
    )
    fund_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Fund display name"
    )
    buy_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Initial purchase date"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, comment="Total invested amount (CNY)"
    )
    shares: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, comment="Current shares held"
    )
    buy_nav: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), default=None, comment="Purchase NAV at time of entry"
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


class FundTransaction(Base):
    """Individual buy/sell transaction for a holding."""

    __tablename__ = "fund_transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('buy', 'sell')",
            name="ck_fund_transaction_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    holding_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("holdings.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to holdings.id",
    )
    type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="Transaction type: buy or sell"
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Transaction date"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, comment="Transaction amount (CNY)"
    )
    shares: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, comment="Transacted shares"
    )
    price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), default=None, comment="Transaction NAV/price"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Record creation timestamp",
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, default=None, nullable=True, comment="Owner user ID"
    )


class FundWatchlist(Base):
    """Funds the user is tracking but has not yet purchased."""

    __tablename__ = "fund_watchlists"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    fund_code: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True, comment="Fund ticker code (MVP: single-user; multi-user: add composite unique with user_id)"
    )
    fund_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Fund display name"
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="When this fund was added to the watchlist",
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, default=None, nullable=True, comment="Owner user ID"
    )
