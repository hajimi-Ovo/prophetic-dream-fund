"""
Pydantic schemas for the holding (持仓) module.

All request/response models used by /holdings, /watchlist, and /dashboard endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Holding CRUD schemas
# ---------------------------------------------------------------------------
class HoldingCreate(BaseModel):
    """Request body for creating a new holding."""

    fund_code: str = Field(..., min_length=1, max_length=10, description="Fund ticker code")
    fund_name: str = Field(..., min_length=1, max_length=100, description="Fund display name")
    buy_date: date = Field(..., description="Initial purchase date")
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2, description="Total invested amount (CNY)")
    shares: Decimal = Field(..., gt=0, max_digits=18, decimal_places=4, description="Current shares held")
    buy_nav: Decimal | None = Field(None, max_digits=10, decimal_places=4, description="Purchase NAV at entry time")


class HoldingUpdate(BaseModel):
    """Request body for updating an existing holding.

    NOTE: fund_code is intentionally excluded — it cannot be changed after creation.
    """

    amount: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=2, description="Total invested amount")
    shares: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=4, description="Current shares held")
    buy_date: date | None = Field(None, description="Purchase date")
    buy_nav: Decimal | None = Field(None, max_digits=10, decimal_places=4, description="Purchase NAV")


class HoldingResponse(BaseModel):
    """Single holding with real-time profit/loss data."""

    id: int = Field(..., description="Holding record ID")
    fund_code: str = Field(..., description="Fund ticker code")
    fund_name: str = Field(..., description="Fund display name")
    buy_date: date = Field(..., description="Initial purchase date")
    amount: Decimal = Field(..., description="Total invested amount")
    shares: Decimal = Field(..., description="Current shares held")
    buy_nav: Decimal | None = Field(None, description="Purchase NAV")
    latest_nav: Decimal | None = Field(None, description="Latest market NAV")
    market_value: Decimal | None = Field(None, description="Current market value = shares * latest_nav")
    profit_loss: Decimal | None = Field(None, description="Unrealized P&L = market_value - amount")
    profit_loss_ratio: Decimal | None = Field(None, description="P&L ratio = profit_loss / amount")
    holding_ratio: Decimal | None = Field(None, description="Weight of this holding in total portfolio")
    created_at: datetime | None = Field(None, description="Record creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")

    model_config = {"from_attributes": True}


class HoldingSummary(BaseModel):
    """Summary statistics for the holdings list."""

    total_asset: Decimal = Field(Decimal("0"), description="Total portfolio market value")
    total_cost: Decimal = Field(Decimal("0"), description="Total invested cost")
    total_profit: Decimal = Field(Decimal("0"), description="Total unrealized profit")
    total_profit_ratio: Decimal | None = Field(None, description="Unrealized profit ratio")
    today_profit: Decimal | None = Field(None, description="Today's profit estimate")
    today_profit_ratio: Decimal | None = Field(None, description="Today's profit ratio")
    holding_count: int = Field(0, description="Number of holdings")
    best_fund: dict[str, Any] | None = Field(None, description="Best performing fund")
    worst_fund: dict[str, Any] | None = Field(None, description="Worst performing fund")


class HoldingListResponse(BaseModel):
    """Response body for listing all holdings."""

    items: list[HoldingResponse] = Field(default_factory=list, description="Holdings with P&L data")
    summary: HoldingSummary = Field(default_factory=HoldingSummary, description="Aggregate portfolio summary")


# ---------------------------------------------------------------------------
# Watchlist schemas
# ---------------------------------------------------------------------------
class WatchlistCreate(BaseModel):
    """Request body for adding a fund to the watchlist."""

    fund_code: str = Field(..., min_length=1, max_length=10, description="Fund ticker code")
    fund_name: str = Field(..., min_length=1, max_length=100, description="Fund display name")


class WatchlistResponse(BaseModel):
    """Single watchlist item with latest market data."""

    fund_code: str = Field(..., description="Fund ticker code")
    fund_name: str = Field(..., description="Fund display name")
    latest_nav: Decimal | None = Field(None, description="Latest market NAV")
    daily_return: Decimal | None = Field(None, description="Daily return")
    added_at: datetime | None = Field(None, description="When added to watchlist")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------
class DashboardSummary(BaseModel):
    """Dashboard summary aggregation."""

    total_asset: Decimal = Field(Decimal("0"), description="Total portfolio market value")
    total_cost: Decimal = Field(Decimal("0"), description="Total invested cost")
    total_profit: Decimal = Field(Decimal("0"), description="Total unrealized profit")
    total_profit_ratio: Decimal | None = Field(None, description="Unrealized profit ratio")
    today_profit: Decimal = Field(Decimal("0"), description="Today's profit estimate")
    today_profit_ratio: Decimal | None = Field(None, description="Today's profit ratio")
    holding_count: int = Field(0, description="Number of holdings")


class ReturnsChartPoint(BaseModel):
    """Single point on the returns chart."""

    nav_date: date = Field(..., alias="date", description="Valuation date")
    portfolio_nav: Decimal = Field(..., description="Composite portfolio NAV")
    benchmark_nav: Decimal | None = Field(None, description="Benchmark NAV (e.g. HS300)")

    model_config = {"populate_by_name": True}


class ReturnsChartData(BaseModel):
    """Cumulative returns curve data."""

    period: str = Field(..., description="Chart period (1m, 3m, 6m, 1y, all)")
    points: list[ReturnsChartPoint] = Field(default_factory=list, description="NAV data points")
    benchmark_points: list[ReturnsChartPoint] = Field(default_factory=list, description="Benchmark NAV data points")


class AllocationItem(BaseModel):
    """Single allocation category for the pie chart."""

    type: str = Field(..., description="Fund type / category name")
    ratio: Decimal = Field(..., description="Percentage of total portfolio")
    amount: Decimal = Field(..., description="Market value in this category")
    fund_count: int = Field(0, description="Number of funds in this category")


class AllocationData(BaseModel):
    """Portfolio allocation breakdown."""

    items: list[AllocationItem] = Field(default_factory=list, description="Allocation categories")


class PortfolioRiskMetrics(BaseModel):
    """Portfolio-level risk metrics."""

    max_drawdown: Decimal | None = Field(None, description="Maximum drawdown of portfolio")
    sharpe_ratio: float | None = Field(None, description="Sharpe ratio (annualized)")
    volatility: float | None = Field(None, description="Annualized volatility")
