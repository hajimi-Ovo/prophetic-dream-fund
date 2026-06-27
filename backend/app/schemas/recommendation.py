"""
Pydantic schemas for the 智能推荐 (Smart Recommendation) module.

All request/response models used by /recommend endpoints.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Risk Assessment
# ---------------------------------------------------------------------------
class RiskAssessmentRequest(BaseModel):
    """Request body for risk profile assessment."""

    risk_tolerance: str = Field(
        ...,
        description="Risk tolerance: conservative, moderate, aggressive",
        pattern=r"^(conservative|moderate|aggressive)$",
    )
    investment_horizon: str = Field(
        ...,
        description="Investment time horizon: short, medium, long, very_long",
        pattern=r"^(short|medium|long|very_long)$",
    )
    return_expectation: str = Field(
        ...,
        description="Return expectation: conservative, balanced, growth, aggressive",
        pattern=r"^(conservative|balanced|growth|aggressive)$",
    )


class RiskAssessmentResponse(BaseModel):
    """Response for risk profile assessment."""

    risk_level: str = Field(..., description="Assessed risk level")
    suggested_allocation: dict[str, Decimal] = Field(
        ...,
        description="Suggested allocation ratios by fund type",
    )
    user_id: int | None = Field(None, description="Owner user ID")
    updated_at: datetime | None = Field(None, description="Last update timestamp")


# ---------------------------------------------------------------------------
# Recommended Fund Item
# ---------------------------------------------------------------------------
class RecommendItem(BaseModel):
    """A single recommended fund entry."""

    fund_code: str = Field(..., description="Fund ticker code")
    fund_name: str = Field(..., description="Fund display name")
    score: Decimal = Field(..., description="Composite recommendation score")
    reasons: list[str] = Field(
        default_factory=list, description="Human-readable reasons for recommendation"
    )
    risk_match: str = Field(
        ..., description="Risk match level: high, medium, low"
    )
    suggested_action: str = Field(
        ...,
        description="Suggested action: buy, accumulate, hold, wait, sell",
    )
    suggested_amount: Decimal | None = Field(
        None, description="Suggested investment amount in CNY"
    )


class RecommendListResponse(BaseModel):
    """Response containing a list of recommended funds."""

    items: list[RecommendItem] = Field(
        default_factory=list, description="Recommended fund items"
    )
    strategy: str = Field("hybrid", description="Strategy used: hybrid, value, growth")
    total: int = Field(0, description="Total number of recommendations")


# ---------------------------------------------------------------------------
# Timing Advice
# ---------------------------------------------------------------------------
class TimingAdviceResponse(BaseModel):
    """Timing advice for a specific fund."""

    fund_code: str = Field(..., description="Fund ticker code")
    fund_name: str = Field("", description="Fund display name")
    valuation_percentile: float = Field(
        ..., description="Current NAV valuation percentile (0-100)"
    )
    signal: str = Field(
        ...,
        description=(
            "Timing signal: strong_buy, buy, accumulate, hold, reduce, wait, sell"
        ),
    )
    trend_signal: str = Field(
        ...,
        description="Trend signal: golden_cross, dead_cross, neutral",
    )
    reasons: list[str] = Field(
        default_factory=list, description="Timing signal rationale"
    )


# ---------------------------------------------------------------------------
# Portfolio Plan
# ---------------------------------------------------------------------------
class AllocationItem(BaseModel):
    """A single allocation entry in the portfolio plan."""

    fund_code: str = Field(..., description="Fund ticker code")
    fund_name: str = Field(..., description="Fund display name")
    ratio: Decimal = Field(..., description="Allocation ratio (0-1)")
    amount: Decimal = Field(..., description="Allocated amount in CNY")
    reason: str = Field("", description="Reason for this allocation")


class PortfolioPlanResponse(BaseModel):
    """Portfolio construction / optimization result."""

    total_amount: Decimal = Field(..., description="Total portfolio amount in CNY")
    allocations: list[AllocationItem] = Field(
        default_factory=list, description="Allocation entries"
    )
    expected_return: float = Field(0.0, description="Expected annualized return")
    expected_risk: float = Field(0.0, description="Expected annualized volatility")
    max_drawdown_estimate: float = Field(0.0, description="Estimated max drawdown")
    rebalance_suggestions: list[str] = Field(
        default_factory=list, description="Rebalancing suggestions"
    )


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------
class BacktestResponse(BaseModel):
    """Historical backtest simulation result."""

    strategy: str = Field(..., description="Strategy name: hybrid, value, growth")
    period: str = Field(..., description="Backtest period: 1y, 3y, 5y")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    total_return: Decimal = Field(..., description="Cumulative total return")
    annual_return: float = Field(..., description="Annualized return")
    max_drawdown: Decimal = Field(..., description="Maximum drawdown")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    win_rate: float = Field(..., description="Win rate (fraction of positive months)")
    nav_series: list[dict[str, object]] = Field(
        default_factory=list, description="Portfolio NAV series over time"
    )
    benchmark_series: list[dict[str, object]] = Field(
        default_factory=list, description="Benchmark NAV series for comparison"
    )
