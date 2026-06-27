"""
Pydantic schemas for the fund market (行情) module.

All request/response models used by /funds endpoints.
"""

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class FundSortBy(str, Enum):
    """Allowed sort fields for fund filtering."""
    LATEST_NAV = "latest_nav"
    DAILY_RETURN = "daily_return"
    ONE_YEAR_RETURN = "one_year_return"
    THREE_YEAR_RETURN = "three_year_return"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


# ---------------------------------------------------------------------------
# Basic fund info
# ---------------------------------------------------------------------------
class FundBasic(BaseModel):
    """Compact fund information for list/search views."""
    code: str = Field(..., description="Fund ticker code")
    name: str = Field(..., description="Fund display name")
    type: str = Field(..., description="Fund type (e.g. stock, bond, hybrid)")
    scale: Decimal | None = Field(None, description="Fund AUM / scale in CNY")
    fee_rate: Decimal | None = Field(None, description="Management fee rate")
    company: str | None = Field(None, description="Fund management company")
    latest_nav: Decimal | None = Field(None, description="Latest unit NAV")
    daily_return: Decimal | None = Field(None, description="Daily return (decimal)")
    ytd_return: Decimal | None = Field(None, description="Year-to-date return")
    one_year_return: Decimal | None = Field(None, description="One-year return")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Fund detail (aggregated)
# ---------------------------------------------------------------------------
class NavInfo(BaseModel):
    """NAV detail block within FundDetail."""
    latest_nav: Decimal | None = Field(None, description="Latest unit NAV")
    accumulated_nav: Decimal | None = Field(None, description="Latest accumulated NAV")
    daily_return: Decimal | None = Field(None, description="Daily return")
    weekly_return: Decimal | None = Field(None, description="Weekly return")
    monthly_return: Decimal | None = Field(None, description="Monthly return")
    three_month_return: Decimal | None = Field(None, description="3-month return")
    six_month_return: Decimal | None = Field(None, description="6-month return")
    ytd_return: Decimal | None = Field(None, description="Year-to-date return")
    one_year_return: Decimal | None = Field(None, description="1-year return")
    three_year_return: Decimal | None = Field(None, description="3-year return")
    five_year_return: Decimal | None = Field(None, description="5-year return")


class ManagerInfo(BaseModel):
    """Fund manager info block within FundDetail."""
    name: str | None = Field(None, description="Manager name")
    start_date: date | None = Field(None, description="Start date managing this fund")
    tenure_return: Decimal | None = Field(None, description="Return during tenure")


class RiskMetrics(BaseModel):
    """Risk assessment metrics block within FundDetail."""
    max_drawdown: Decimal | None = Field(None, description="Maximum drawdown")
    sharpe_ratio: float | None = Field(None, description="Sharpe ratio")
    volatility: float | None = Field(None, description="Annualized volatility")
    alpha: float | None = Field(None, description="Alpha (excess return)")
    beta: float | None = Field(None, description="Beta (market sensitivity)")


class FundDetail(BaseModel):
    """Full fund detail aggregation."""
    basic: FundBasic = Field(..., description="Basic fund information")
    nav: NavInfo | None = Field(None, description="NAV and return data")
    manager: ManagerInfo | None = Field(None, description="Fund manager info")
    risk_metrics: RiskMetrics | None = Field(None, description="Risk assessment metrics")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Filter params
# ---------------------------------------------------------------------------
class FundFilterParams(BaseModel):
    """Query parameters for multi-dimension fund filtering."""
    type: str | None = Field(None, description="Fund type filter")
    min_scale: Decimal | None = Field(None, description="Minimum AUM/scale")
    max_scale: Decimal | None = Field(None, description="Maximum AUM/scale")
    max_fee: Decimal | None = Field(None, description="Maximum management fee rate")
    manager: str | None = Field(None, description="Manager name filter (LIKE)")
    company: str | None = Field(None, description="Company name filter (LIKE)")
    sort_by: FundSortBy | None = Field(None, description="Field to sort by")
    order: SortOrder = Field(SortOrder.DESC, description="Sort direction")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @field_validator("min_scale", "max_scale", "max_fee", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        """Allow string or int inputs for Decimal fields."""
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return Decimal(str(v))


# ---------------------------------------------------------------------------
# NAV history
# ---------------------------------------------------------------------------
class NavHistoryPoint(BaseModel):
    """Single NAV data point in a history series."""
    nav_date: date = Field(..., alias="date", description="NAV valuation date")
    nav: Decimal = Field(..., description="Unit NAV")
    accumulated_nav: Decimal | None = Field(None, description="Accumulated NAV")

    model_config = {"populate_by_name": True}


class NavHistoryResponse(BaseModel):
    """NAV history response with period label and data points."""
    period: str = Field(..., description="Requested period (1m, 3m, 6m, 1y, all)")
    points: list[NavHistoryPoint] = Field(
        default_factory=list, description="NAV data points"
    )


# ---------------------------------------------------------------------------
# Fund comparison
# ---------------------------------------------------------------------------
class FundCompareItem(BaseModel):
    """Side-by-side fund metrics for comparison."""
    code: str = Field(..., description="Fund code")
    name: str = Field(..., description="Fund name")
    latest_nav: Decimal | None = Field(None, description="Latest NAV")
    daily_return: Decimal | None = Field(None, description="Daily return")
    weekly_return: Decimal | None = Field(None, description="Weekly return")
    monthly_return: Decimal | None = Field(None, description="Monthly return")
    ytd_return: Decimal | None = Field(None, description="Year-to-date return")
    one_year_return: Decimal | None = Field(None, description="1-year return")
    max_drawdown: Decimal | None = Field(None, description="Maximum drawdown")
    volatility: float | None = Field(None, description="Annualized volatility")
    sharpe_ratio: float | None = Field(None, description="Sharpe ratio")


class CompareResponse(BaseModel):
    """Multi-fund comparison response."""
    funds: list[FundCompareItem] = Field(
        default_factory=list, description="Fund comparison items"
    )
    overlay_points: dict[str, list[NavHistoryPoint]] = Field(
        default_factory=dict,
        description="NAV series keyed by fund code for chart overlay",
    )


# ---------------------------------------------------------------------------
# Portfolio / holdings
# ---------------------------------------------------------------------------
class FundPortfolioItem(BaseModel):
    """Single holding in a fund's portfolio."""
    stock_code: str | None = Field(None, description="Stock / asset code")
    stock_name: str | None = Field(None, description="Stock / asset name")
    ratio: Decimal | None = Field(None, description="Weight in portfolio")


# ---------------------------------------------------------------------------
# Search result (extends FundBasic)
# ---------------------------------------------------------------------------
class FundSearchResult(FundBasic):
    """Search result item — extends FundBasic."""
    pass
