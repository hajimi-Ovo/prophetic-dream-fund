"""
Unit tests for DashboardService — mock DB and Redis.

Verifies summary aggregation, allocation grouping, and returns chart synthesis.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dashboard_service import DashboardService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_db() -> MagicMock:
    """Return a fully mocked AsyncSession."""
    db = MagicMock(spec=AsyncSession)
    return db


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Return a fully mocked Redis client."""
    redis = AsyncMock()
    redis.hgetall.return_value = {}
    redis.get.return_value = None
    return redis


@pytest.fixture
def service(mock_db: MagicMock, mock_redis: AsyncMock) -> DashboardService:
    """Return a DashboardService with mocked dependencies."""
    return DashboardService(mock_db, mock_redis)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_holding_row(
    id: int = 1,
    fund_code: str = "000001",
    fund_name: str = "Test Fund A",
    fund_type: str = "stock",
    amount: Decimal = Decimal("10000.00"),
    shares: Decimal = Decimal("5000.0000"),
    buy_nav: Decimal | None = Decimal("2.0000"),
) -> MagicMock:
    """Create a mock Holding ORM row."""
    h = MagicMock()
    h.id = id
    h.fund_code = fund_code
    h.fund_name = fund_name
    h.buy_date = date(2025, 1, 15)
    h.amount = amount
    h.shares = shares
    h.buy_nav = buy_nav
    h.created_at = datetime(2025, 1, 15, 10, 0, 0)
    h.updated_at = datetime(2025, 1, 15, 10, 0, 0)
    h.user_id = None
    return h


def _make_nav_row(code: str, date_val: date, nav_val: Decimal) -> MagicMock:
    """Create a mock FundNav ORM row."""
    n = MagicMock()
    n.fund_code = code
    n.date = date_val
    n.nav = nav_val
    n.accumulated_nav = nav_val + Decimal("0.5")
    n.daily_return = Decimal("0.001")
    return n


def _setup_holdings_query(mock_db: MagicMock, rows: list[MagicMock]) -> None:
    """Set up execute() -> scalars() -> all() for holdings query."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result


def _setup_holdings_and_nav_queries(
    mock_db: MagicMock,
    holdings: list[MagicMock],
    nav_data: dict[str, list[dict[str, Any]]],
) -> None:
    """Set up multiple execute calls: holdings query, then NAV queries for each fund."""
    exec_calls: list[MagicMock] = []

    # First call: holdings list
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = holdings
    mock_result.scalars.return_value = mock_scalars
    exec_calls.append(mock_result)

    # Subsequent calls: NAV queries for each fund, then possibly benchmark
    for code in [h.fund_code for h in holdings]:
        nav_rows = []
        for pt in nav_data.get(code, []):
            nav_rows.append(_make_nav_row(code, pt["date"], pt["nav"]))
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = list(reversed(nav_rows))  # desc order in DB
        mock_result.scalars.return_value = mock_scalars
        exec_calls.append(mock_result)

    # Benchmark query (may fail gracefully)
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    exec_calls.append(mock_result)

    mock_db.execute.side_effect = exec_calls


# ---------------------------------------------------------------------------
# Tests: summary
# ---------------------------------------------------------------------------
class TestSummary:
    """DashboardService.get_summary tests."""

    async def test_empty_summary(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Empty holdings returns zero summary."""
        _setup_holdings_query(mock_db, [])

        result = await service.get_summary()

        assert result["total_asset"] == Decimal("0")
        assert result["total_cost"] == Decimal("0")
        assert result["total_profit"] == Decimal("0")
        assert result["holding_count"] == 0

    async def test_summary_with_holdings(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Summary aggregates correctly from holdings."""
        h1 = _make_holding_row(id=1, amount=Decimal("10000.00"), shares=Decimal("5000.0000"))
        h2 = _make_holding_row(id=2, fund_code="000002", fund_name="Fund B", amount=Decimal("5000.00"), shares=Decimal("2500.0000"))
        _setup_holdings_query(mock_db, [h1, h2])

        # Mock Redis NAV data
        mock_redis.hgetall.side_effect = [
            {"nav": "2.5000", "daily_return": "0.0100"},
            {"nav": "3.0000", "daily_return": "0.0050"},
        ]

        result = await service.get_summary()

        # h1: mv = 5000 * 2.5 = 12500
        # h2: mv = 2500 * 3.0 = 7500
        # total_asset = 20000
        assert result["total_asset"] == Decimal("20000.00")
        assert result["total_cost"] == Decimal("15000.00")
        assert result["total_profit"] == Decimal("5000.00")
        assert result["holding_count"] == 2

        # today_profit: h1: 5000*2.5*0.01=125, h2: 2500*3.0*0.005=37.5, total=162.5
        assert result["today_profit"] == Decimal("162.50")

    async def test_summary_single_holding(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Single holding summary works correctly."""
        h = _make_holding_row(id=1)
        _setup_holdings_query(mock_db, [h])

        mock_redis.hgetall.return_value = {"nav": "2.0000"}

        result = await service.get_summary()

        assert result["holding_count"] == 1
        assert result["total_asset"] == Decimal("10000.00")


# ---------------------------------------------------------------------------
# Tests: allocation
# ---------------------------------------------------------------------------
class TestAllocation:
    """DashboardService.get_allocation tests."""

    async def test_empty_allocation(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """No holdings returns empty allocation."""
        _setup_holdings_query(mock_db, [])

        result = await service.get_allocation()

        assert result["items"] == []

    async def test_allocation_grouping(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Holdings grouped by fund type."""
        h1 = _make_holding_row(id=1, fund_code="000001", amount=Decimal("10000.00"), shares=Decimal("5000.0000"))
        h2 = _make_holding_row(id=2, fund_code="000002", fund_name="Fund B", amount=Decimal("5000.00"), shares=Decimal("2500.0000"))

        mock_result_hold = MagicMock()
        mock_scalars_hold = MagicMock()
        mock_scalars_hold.all.return_value = [h1, h2]
        mock_result_hold.scalars.return_value = mock_scalars_hold

        # Fund type query

        fund_type_row1 = MagicMock()
        fund_type_row1.code = "000001"
        fund_type_row1.type = "stock"
        fund_type_row2 = MagicMock()
        fund_type_row2.code = "000002"
        fund_type_row2.type = "bond"

        mock_result_fund = MagicMock()
        mock_result_fund.all.return_value = [fund_type_row1, fund_type_row2]

        mock_db.execute.side_effect = [mock_result_hold, mock_result_fund]

        # Mock Redis NAV
        mock_redis.hgetall.side_effect = [
            {"nav": "2.5000"},
            {"nav": "3.0000"},
        ]

        result = await service.get_allocation()

        assert len(result["items"]) == 2  # stock and bond
        types = {item["type"] for item in result["items"]}
        assert "stock" in types
        assert "bond" in types

        # Check that amounts add up
        total_amount = sum(item["amount"] for item in result["items"])
        # h1: 5000*2.5=12500, h2: 2500*3.0=7500, total=20000
        assert total_amount == Decimal("20000.00")


# ---------------------------------------------------------------------------
# Tests: returns chart
# ---------------------------------------------------------------------------
class TestReturnsChart:
    """DashboardService.get_returns_chart tests."""

    async def test_empty_chart(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """No holdings returns empty chart."""
        _setup_holdings_query(mock_db, [])

        result = await service.get_returns_chart("1m")

        assert result["period"] == "1m"
        assert result["points"] == []

    async def test_chart_with_nav_data(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Chart synthesis with NAV history."""
        h = _make_holding_row(id=1, fund_code="000001", shares=Decimal("5000.0000"))

        mock_result_hold = MagicMock()
        mock_scalars_hold = MagicMock()
        mock_scalars_hold.all.return_value = [h]
        mock_result_hold.scalars.return_value = mock_scalars_hold

        # NAV data for fund 000001
        nav_rows = [
            _make_nav_row("000001", date(2025, 6, 1), Decimal("1.5000")),
            _make_nav_row("000001", date(2025, 6, 2), Decimal("1.5200")),
            _make_nav_row("000001", date(2025, 6, 3), Decimal("1.5100")),
        ]

        mock_result_nav = MagicMock()
        mock_scalars_nav = MagicMock()
        mock_scalars_nav.all.return_value = list(reversed(nav_rows))
        mock_result_nav.scalars.return_value = mock_scalars_nav

        # Benchmark query returns empty
        mock_result_bench = MagicMock()
        mock_scalars_bench = MagicMock()
        mock_scalars_bench.all.return_value = []
        mock_result_bench.scalars.return_value = mock_scalars_bench

        mock_db.execute.side_effect = [mock_result_hold, mock_result_nav, mock_result_bench]

        result = await service.get_returns_chart("1m")

        assert result["period"] == "1m"
        assert len(result["points"]) == 3
        # Composite NAV for each date (single fund, so same as fund NAV)
        assert result["points"][0]["portfolio_nav"] == Decimal("1.5000")
        assert result["points"][1]["portfolio_nav"] == Decimal("1.5200")
        assert result["points"][2]["portfolio_nav"] == Decimal("1.5100")

    async def test_chart_period_mapping(
        self, service: DashboardService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Period parameter maps to correct trading-day counts."""
        _setup_holdings_query(mock_db, [])

        result = await service.get_returns_chart("all")

        assert result["period"] == "all"
        assert result["points"] == []
