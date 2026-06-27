"""
Unit tests for FundService — mock DB and Redis.

Verifies search, filter, detail, compare, portfolio, and nav-history flows.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.fund import FundFilterParams
from app.services.fund_service import FundService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_db() -> MagicMock:
    """Return a fully mocked AsyncSession with proper execute chain."""
    db = MagicMock(spec=AsyncSession)

    # Set up execute() → Result → scalars() → ScalarResult → all()
    def _make_execute_result(rows: list[Any] | None = None, scalar_val: Any = None) -> MagicMock:
        result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = rows or []
        result.scalars.return_value = scalars_mock
        result.scalar.return_value = scalar_val
        return result

    db.execute.return_value = _make_execute_result()

    return db


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Return a fully mocked Redis client."""
    redis = AsyncMock()
    redis.hgetall.return_value = {}
    redis.get.return_value = None
    redis.zrange.return_value = []
    return redis


@pytest.fixture
def service(mock_db: MagicMock, mock_redis: AsyncMock) -> FundService:
    """Return a FundService with mocked dependencies."""
    return FundService(mock_db, mock_redis)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_fund_row(code: str, name: str, **kwargs: Any) -> MagicMock:
    """Create a mock Fund ORM row."""
    f = MagicMock()
    f.code = code
    f.name = name
    f.type = kwargs.get("type", "stock")
    f.scale = kwargs.get("scale", Decimal("1000000000"))
    f.fee_rate = kwargs.get("fee_rate", Decimal("0.015"))
    f.company = kwargs.get("company", "Test Fund Co")
    return f


def _setup_mock_query(mock_db: MagicMock, rows: list[MagicMock], scalar_value: Any = None) -> None:
    """Set up mock DB execute() -> scalars() -> all() chain to return *rows*."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar.return_value = scalar_value
    mock_db.execute.return_value = mock_result


# ---------------------------------------------------------------------------
# Tests: search
# ---------------------------------------------------------------------------
class TestSearch:
    """FundService.search tests."""

    async def test_search_with_cache_hit(
        self, service: FundService, mock_redis: AsyncMock
    ) -> None:
        """Search returns cached results when available."""
        mock_redis.get.return_value = (
            '[{"code":"000001","name":"Test Fund A","type":"stock"},'
            '{"code":"000002","name":"Test Fund B","type":"bond"}]'
        )
        mock_redis.hgetall.side_effect = [
            {b"nav": b"1.5000", b"daily_return": b"0.0012"},
            {b"nav": b"2.0000", b"daily_return": b"-0.0005"},
        ]

        result = await service.search("Test", page=1, page_size=10)

        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "Test Fund A"

    async def test_search_empty_keyword(
        self, service: FundService, mock_redis: AsyncMock
    ) -> None:
        """Empty keyword falls through to DB (as designed)."""
        mock_redis.get.return_value = (
            '[{"code":"000001","name":"Fund A","type":"stock"}]'
        )
        # Empty keyword should trigger DB fallback, returning mock rows
        mock_rows = [_make_fund_row("000001", "Fund A")]
        mock_db = service.db
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_rows
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        result = await service.search("", page=1, page_size=10)
        assert result["total"] == 1

    async def test_search_no_match(
        self, service: FundService, mock_redis: AsyncMock
    ) -> None:
        """Keyword matching nothing returns empty."""
        mock_redis.get.return_value = (
            '[{"code":"000001","name":"Fund A","type":"stock"}]'
        )

        result = await service.search("XYZ_Nonexistent", page=1, page_size=10)
        assert result["total"] == 0
        assert result["items"] == []

    async def test_search_pagination(
        self, service: FundService, mock_redis: AsyncMock
    ) -> None:
        """Pagination slices results correctly."""
        items = [{"code": f"{i:06d}", "name": f"Fund {i}", "type": "stock"} for i in range(25)]
        import json
        mock_redis.get.return_value = json.dumps(items)

        result = await service.search("Fund", page=2, page_size=10)
        assert result["total"] == 25
        assert len(result["items"]) == 10
        # Second page should start from index 10
        assert result["items"][0]["code"] == "000010"


# ---------------------------------------------------------------------------
# Tests: filter_funds
# ---------------------------------------------------------------------------
class TestFilter:
    """FundService.filter_funds tests."""

    async def test_filter_by_type(
        self, service: FundService, mock_db: AsyncSession
    ) -> None:
        """Filter by fund type."""
        from unittest.mock import MagicMock

        # Mock the count query result (scalar)
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 5
        mock_db.execute.side_effect = [
            # count query
            MagicMock(scalar=MagicMock(return_value=5)),
            # data query
            MagicMock(**{
                "all.return_value": [
                    MagicMock(
                        code="000001", name="Fund A", type="stock",
                        scale=Decimal("1000000"), fee_rate=Decimal("0.015"),
                        company="Co A", latest_nav=Decimal("1.5"), daily_return=Decimal("0.001"),
                    ),
                    MagicMock(
                        code="000002", name="Fund B", type="stock",
                        scale=Decimal("2000000"), fee_rate=Decimal("0.010"),
                        company="Co B", latest_nav=Decimal("2.0"), daily_return=Decimal("0.002"),
                    ),
                ]
            }),
        ]

        filters = FundFilterParams(type="stock", page=1, page_size=20)
        result = await service.filter_funds(filters)

        assert result["total"] == 5
        assert len(result["items"]) == 2
        assert result["items"][0]["code"] == "000001"


# ---------------------------------------------------------------------------
# Tests: get_detail
# ---------------------------------------------------------------------------
class TestDetail:
    """FundService.get_detail tests."""

    async def test_fund_not_found(
        self, service: FundService, mock_db: AsyncSession
    ) -> None:
        """Non-existent fund returns empty dict."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = await service.get_detail("NONEXIST")
        assert result == {}

    async def test_full_detail(
        self, service: FundService, mock_db: AsyncSession
    ) -> None:
        """Full detail aggregation returns all sections."""
        fund_row = _make_fund_row("000001", "Test Fund")

        nav_row = MagicMock()
        nav_row.nav = Decimal("1.5000")
        nav_row.accumulated_nav = Decimal("2.1000")
        nav_row.daily_return = Decimal("0.0012")

        manager_row = MagicMock()
        manager_row.name = "Manager A"
        manager_row.start_date = date(2020, 1, 1)
        manager_row.tenure_return = Decimal("0.4500")

        # We need 22+ nav history points for risk metrics
        nav_history = []
        base = Decimal("1.00")
        for i in range(30):
            m = MagicMock()
            m.date = date(2025, 1, 1) + __import__("datetime").timedelta(days=i)
            m.nav = base + Decimal(str(i * 0.005))
            m.accumulated_nav = m.nav + Decimal("0.5")
            m.daily_return = Decimal("0.005") if i > 0 else None
            nav_history.append(m)

        # Order of queries:
        # 1. fund query -> fund_row
        # 2. latest nav query -> nav_row
        # 3. nav history query (limit=1260) -> nav_history
        # 4. manager query -> manager_row
        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=fund_row)),   # fund
            MagicMock(scalar_one_or_none=MagicMock(return_value=nav_row)),    # latest nav
            MagicMock(**{"scalars.return_value.all.return_value": nav_history}),  # nav history
            MagicMock(scalar_one_or_none=MagicMock(return_value=manager_row)), # manager
        ]

        result = await service.get_detail("000001")

        assert "basic" in result
        assert "nav" in result
        assert "manager" in result
        assert "risk_metrics" in result
        assert result["basic"]["code"] == "000001"
        assert result["manager"]["name"] == "Manager A"


# ---------------------------------------------------------------------------
# Tests: get_nav_history
# ---------------------------------------------------------------------------
class TestNavHistory:
    """FundService.get_nav_history tests."""

    async def test_period_1m_from_cache(
        self, service: FundService, mock_redis: AsyncMock
    ) -> None:
        """1m period should try Redis cache first."""
        mock_redis.zrange.return_value = [
            '{"date":"2025-06-01","nav":"1.00","accumulated_nav":"1.50"}',
            '{"date":"2025-06-02","nav":"1.01","accumulated_nav":"1.51"}',
        ]

        result = await service.get_nav_history("000001", period="1m")
        assert result["period"] == "1m"
        assert len(result["points"]) == 2

    async def test_unrecognized_period(
        self, service: FundService, mock_db: AsyncSession
    ) -> None:
        """Unknown period defaults to 22 trading days."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = await service.get_nav_history("000001", period="unknown")
        assert result["period"] == "unknown"
        assert result["points"] == []


# ---------------------------------------------------------------------------
# Tests: compare
# ---------------------------------------------------------------------------
class TestCompare:
    """FundService.compare tests."""

    async def test_compare_two_funds(
        self, service: FundService, mock_db: AsyncSession
    ) -> None:
        """Compare two funds returns side-by-side data."""
        fund_a = _make_fund_row("000001", "Fund A")
        fund_b = _make_fund_row("000002", "Fund B", type="bond")

        latest_nav_a = MagicMock()
        latest_nav_a.nav = Decimal("1.50")
        latest_nav_a.daily_return = Decimal("0.001")

        latest_nav_b = MagicMock()
        latest_nav_b.nav = Decimal("2.00")
        latest_nav_b.daily_return = Decimal("-0.002")

        # We need at least 22 nav points for risk metric calculation
        nav_pts_a = []
        nav_pts_b = []
        for i in range(30):
            m = MagicMock()
            m.date = date(2025, 1, 1) + __import__("datetime").timedelta(days=i)
            m.nav = Decimal(str(1.0 + i * 0.01))
            m.accumulated_nav = m.nav + Decimal("0.5")
            m.daily_return = Decimal("0.01")
            nav_pts_a.append(m)
            nav_pts_b.append(m)

        # Calls: fund_a, latest_nav_a, nav_history_a (252), overlay_a (30),
        #        fund_b, latest_nav_b, nav_history_b (252), overlay_b (30)
        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=fund_a)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=latest_nav_a)),
            MagicMock(**{"scalars.return_value.all.return_value": nav_pts_a}),
            MagicMock(**{"scalars.return_value.all.return_value": nav_pts_a[:30]}),
            MagicMock(scalar_one_or_none=MagicMock(return_value=fund_b)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=latest_nav_b)),
            MagicMock(**{"scalars.return_value.all.return_value": nav_pts_b}),
            MagicMock(**{"scalars.return_value.all.return_value": nav_pts_b[:30]}),
        ]

        result = await service.compare(["000001", "000002"])

        assert len(result["funds"]) == 2
        assert result["funds"][0]["code"] == "000001"
        assert result["funds"][1]["code"] == "000002"
        assert "000001" in result["overlay_points"]
        assert "000002" in result["overlay_points"]


# ---------------------------------------------------------------------------
# Tests: get_portfolio
# ---------------------------------------------------------------------------
class TestPortfolio:
    """FundService.get_portfolio tests."""

    async def test_empty_holdings(
        self, service: FundService, mock_db: AsyncSession
    ) -> None:
        """Fund with no holdings returns empty list."""
        mock_db.execute.return_value.scalar.return_value = None

        result = await service.get_portfolio("000001")
        assert result == []

    async def test_with_holdings(
        self, service: FundService, mock_db: AsyncSession
    ) -> None:
        """Fund with holdings returns them sorted by ratio desc."""
        h1 = MagicMock(stock_code="600519", stock_name="Kweichow Moutai", ratio=Decimal("0.08"))
        h2 = MagicMock(stock_code="000858", stock_name="Wuliangye", ratio=Decimal("0.05"))

        scalar_mock = MagicMock()
        scalar_mock.scalar.return_value = date(2025, 3, 31)
        all_mock = MagicMock()
        all_mock.scalars.return_value.all.return_value = [h1, h2]

        mock_db.execute.side_effect = [scalar_mock, all_mock]

        result = await service.get_portfolio("000001")
        assert len(result) == 2
        assert result[0]["stock_code"] == "600519"
