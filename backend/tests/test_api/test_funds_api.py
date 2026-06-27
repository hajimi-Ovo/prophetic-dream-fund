"""
API integration tests for /funds endpoints.

Uses the test client with in-memory SQLite database.
Test data is inserted before each test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundHolding, FundManager, FundNav


# ---------------------------------------------------------------------------
# Helper: insert test fixtures
# ---------------------------------------------------------------------------
async def _insert_test_fund(db: AsyncSession) -> None:
    """Insert a single test fund."""
    fund = Fund(
        code="000001",
        name="测试基金A",
        type="stock",
        scale=Decimal("5000000000"),
        fee_rate=Decimal("0.0150"),
        company="测试基金公司",
        inception_date=date(2020, 1, 1),
    )
    db.add(fund)
    await db.flush()


async def _insert_test_nav_data(db: AsyncSession) -> None:
    """Insert NAV history for fund 000001."""
    navs = []
    base = Decimal("1.0000")
    for i in range(60):
        d = date(2025, 1, 2) + __import__("datetime").timedelta(days=i)
        navs.append(
            FundNav(
                fund_code="000001",
                date=d,
                nav=base + Decimal(str(i * 0.002)),
                accumulated_nav=base + Decimal(str(i * 0.002 + 0.5)),
                daily_return=Decimal("0.002") if i > 0 else None,
            )
        )
    db.add_all(navs)
    await db.flush()


async def _insert_test_manager(db: AsyncSession) -> None:
    """Insert a manager for fund 000001."""
    mgr = FundManager(
        fund_code="000001",
        name="张三",
        start_date=date(2021, 6, 1),
        tenure_return=Decimal("0.3500"),
    )
    db.add(mgr)
    await db.flush()


async def _insert_test_holdings(db: AsyncSession) -> None:
    """Insert top holdings for fund 000001."""
    holdings = [
        FundHolding(
            fund_code="000001",
            report_date=date(2025, 3, 31),
            stock_code="600519",
            stock_name="贵州茅台",
            ratio=Decimal("0.0850"),
        ),
        FundHolding(
            fund_code="000001",
            report_date=date(2025, 3, 31),
            stock_code="000858",
            stock_name="五粮液",
            ratio=Decimal("0.0520"),
        ),
    ]
    db.add_all(holdings)
    await db.flush()


async def _insert_second_fund(db: AsyncSession) -> None:
    """Insert a second fund for comparison tests."""
    fund = Fund(
        code="000002",
        name="测试基金B",
        type="bond",
        scale=Decimal("3000000000"),
        fee_rate=Decimal("0.0080"),
        company="测试基金公司B",
        inception_date=date(2019, 6, 1),
    )
    db.add(fund)
    await db.flush()

    # Add NAV data
    navs = []
    for i in range(30):
        d = date(2025, 5, 1) + __import__("datetime").timedelta(days=i)
        navs.append(
            FundNav(
                fund_code="000002",
                date=d,
                nav=Decimal("2.0000") + Decimal(str(i * 0.001)),
                accumulated_nav=Decimal("3.0000") + Decimal(str(i * 0.001)),
                daily_return=Decimal("0.001") if i > 0 else None,
            )
        )
    db.add_all(navs)
    await db.flush()


# ---------------------------------------------------------------------------
# Clear test data helper
# ---------------------------------------------------------------------------
async def _clear_funds(db: AsyncSession) -> None:
    """Remove all test data from fund-related tables."""
    for model in (FundHolding, FundManager, FundNav, Fund):
        await db.execute(delete(model))
    await db.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSearchEndpoint:
    """GET /api/v1/funds/search"""

    async def test_search_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Search returns matching funds."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)

        resp = await client.get("/api/v1/funds/search?keyword=测试")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["total"] >= 1

    async def test_search_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Non-matching keyword returns empty results."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)

        resp = await client.get("/api/v1/funds/search?keyword=NONEXISTENT_FUND_XYZ")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["total"] == 0

    async def test_search_pagination(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Pagination parameters are respected."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_second_fund(db_session)

        resp = await client.get("/api/v1/funds/search?keyword=测试&page=1&page_size=1")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 1
        assert len(data["data"]["items"]) == 1


class TestFilterEndpoint:
    """GET /api/v1/funds/filter"""

    async def test_filter_by_type(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Filter by fund type."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)      # stock
        await _insert_second_fund(db_session)      # bond

        resp = await client.get("/api/v1/funds/filter?type=stock")
        data = resp.json()

        assert data["code"] == 0
        items = data["data"]["items"]
        assert all(item["type"] == "stock" for item in items)

    async def test_filter_with_sort(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Filter with sort_by parameter."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_second_fund(db_session)

        resp = await client.get("/api/v1/funds/filter?sort_by=latest_nav&order=desc")
        data = resp.json()

        assert data["code"] == 0


class TestDetailEndpoint:
    """GET /api/v1/funds/{code}"""

    async def test_fund_detail_full(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Full detail with NAV, manager, and risk metrics."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_test_nav_data(db_session)
        await _insert_test_manager(db_session)

        resp = await client.get("/api/v1/funds/000001")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["basic"]["code"] == "000001"
        assert data["data"]["basic"]["name"] == "测试基金A"
        assert data["data"]["manager"]["name"] == "张三"
        assert data["data"]["nav"] is not None
        assert data["data"]["risk_metrics"] is not None

    async def test_fund_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Non-existent fund returns 404."""
        await _clear_funds(db_session)

        resp = await client.get("/api/v1/funds/NONEXIST")
        data = resp.json()

        assert data["code"] == 404
        assert data["data"] is None


class TestNavHistoryEndpoint:
    """GET /api/v1/funds/{code}/nav-history"""

    async def test_nav_history_1m(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """1-month NAV history."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_test_nav_data(db_session)

        resp = await client.get("/api/v1/funds/000001/nav-history?period=1m")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["period"] == "1m"
        assert len(data["data"]["points"]) > 0

    async def test_nav_history_default_period(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Default period (1m) when not specified."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_test_nav_data(db_session)

        resp = await client.get("/api/v1/funds/000001/nav-history")
        data = resp.json()

        assert data["code"] == 0


class TestPortfolioEndpoint:
    """GET /api/v1/funds/{code}/portfolio"""

    async def test_portfolio_with_holdings(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Portfolio returns top holdings."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_test_holdings(db_session)

        resp = await client.get("/api/v1/funds/000001/portfolio")
        data = resp.json()

        assert data["code"] == 0
        items = data["data"]["items"]
        assert len(items) == 2
        assert items[0]["stock_name"] == "贵州茅台"

    async def test_portfolio_empty(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Fund with no holdings returns empty list."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)

        resp = await client.get("/api/v1/funds/000001/portfolio")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["items"] == []


class TestCompareEndpoint:
    """GET /api/v1/funds/compare"""

    async def test_compare_two_funds(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Compare returns side-by-side metrics."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_test_nav_data(db_session)
        await _insert_second_fund(db_session)

        resp = await client.get("/api/v1/funds/compare?codes=000001,000002")
        data = resp.json()

        assert data["code"] == 0
        assert len(data["data"]["funds"]) == 2
        assert "000001" in data["data"]["overlay_points"]
        assert "000002" in data["data"]["overlay_points"]

    async def test_compare_empty_codes(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Empty codes returns error."""
        await _clear_funds(db_session)

        resp = await client.get("/api/v1/funds/compare?codes=")
        data = resp.json()

        assert data["code"] == -1

    async def test_compare_single_fund(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Single fund comparison still works."""
        await _clear_funds(db_session)
        await _insert_test_fund(db_session)
        await _insert_test_nav_data(db_session)

        resp = await client.get("/api/v1/funds/compare?codes=000001")
        data = resp.json()

        assert data["code"] == 0
        assert len(data["data"]["funds"]) == 1
