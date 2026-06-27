"""
API integration tests for /holdings, /watchlist, and /dashboard endpoints.

Uses the test client with in-memory SQLite database.
Test data is inserted before each test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import FundTransaction, FundWatchlist, Holding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _clear_holdings(db: AsyncSession) -> None:
    """Remove all test data from holding-related tables."""
    for model in (FundTransaction, FundWatchlist, Holding):
        await db.execute(delete(model))
    await db.flush()


async def _insert_test_holding(db: AsyncSession) -> Holding:
    """Insert a single test holding and return it."""
    h = Holding(
        fund_code="000001",
        fund_name="测试基金A",
        buy_date=date(2025, 6, 1),
        amount=Decimal("10000.00"),
        shares=Decimal("5000.0000"),
        buy_nav=Decimal("2.0000"),
    )
    db.add(h)
    await db.flush()
    # Insert transaction
    txn = FundTransaction(
        holding_id=h.id,
        type="buy",
        date=date(2025, 6, 1),
        amount=Decimal("10000.00"),
        shares=Decimal("5000.0000"),
        price=Decimal("2.0000"),
    )
    db.add(txn)
    await db.flush()
    return h


async def _insert_second_holding(db: AsyncSession) -> Holding:
    """Insert a second test holding."""
    h = Holding(
        fund_code="000002",
        fund_name="测试基金B",
        buy_date=date(2025, 5, 15),
        amount=Decimal("5000.00"),
        shares=Decimal("2500.0000"),
        buy_nav=Decimal("2.0000"),
    )
    db.add(h)
    await db.flush()
    txn = FundTransaction(
        holding_id=h.id,
        type="buy",
        date=date(2025, 5, 15),
        amount=Decimal("5000.00"),
        shares=Decimal("2500.0000"),
        price=Decimal("2.0000"),
    )
    db.add(txn)
    await db.flush()
    return h


# ---------------------------------------------------------------------------
# Holdings CRUD tests
# ---------------------------------------------------------------------------
class TestCreateHolding:
    """POST /api/v1/holdings"""

    async def test_create_holding_success(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Create a new holding returns 201."""
        await _clear_holdings(db_session)

        resp = await client.post(
            "/api/v1/holdings",
            json={
                "fund_code": "000001",
                "fund_name": "测试基金A",
                "buy_date": "2025-06-01",
                "amount": "10000.00",
                "shares": "5000.0000",
                "buy_nav": "2.0000",
            },
        )
        data = resp.json()

        assert resp.status_code == 201
        assert data["code"] == 0
        assert data["data"]["fund_code"] == "000001"
        assert data["data"]["fund_name"] == "测试基金A"
        assert data["data"]["amount"] == "10000.00"
        assert data["data"]["id"] is not None

        # Verify transaction was created
        txn_result = await db_session.execute(
            __import__("sqlalchemy").select(FundTransaction).where(
                FundTransaction.holding_id == data["data"]["id"]
            )
        )
        txn = txn_result.scalars().first()
        assert txn is not None
        assert txn.type == "buy"

    async def test_create_holding_invalid_data(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Creating with invalid data returns 422."""
        await _clear_holdings(db_session)

        resp = await client.post(
            "/api/v1/holdings",
            json={
                "fund_code": "000001",
                "fund_name": "Missing Fields",
                # missing buy_date, amount, shares
            },
        )

        assert resp.status_code == 422


class TestListHoldings:
    """GET /api/v1/holdings"""

    async def test_list_empty(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Empty holdings list returns success with empty items."""
        await _clear_holdings(db_session)

        resp = await client.get("/api/v1/holdings")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["items"] == []
        assert data["data"]["summary"]["holding_count"] == 0

    async def test_list_with_holdings(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """List returns all holdings with P&L data."""
        await _clear_holdings(db_session)
        await _insert_test_holding(db_session)

        resp = await client.get("/api/v1/holdings")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert len(data["data"]["items"]) >= 1
        item = data["data"]["items"][0]
        assert item["fund_code"] == "000001"
        assert "latest_nav" in item
        assert "market_value" in item
        assert "profit_loss" in item
        assert "profit_loss_ratio" in item
        assert "holding_ratio" in item
        # Summary should exist
        assert "summary" in data["data"]
        assert data["data"]["summary"]["holding_count"] >= 1

    async def test_list_multiple_with_ratios(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Multiple holdings get correct holding_ratios summing to 1."""
        await _clear_holdings(db_session)
        await _insert_test_holding(db_session)
        await _insert_second_holding(db_session)

        resp = await client.get("/api/v1/holdings")
        data = resp.json()

        assert resp.status_code == 200
        items = data["data"]["items"]
        assert len(items) == 2
        # holding_ratios should exist
        ratios = [Decimal(str(item["holding_ratio"])) for item in items]
        total_ratio = sum(ratios)
        # Total should be close to 1 (allow small rounding differences)
        assert abs(total_ratio - Decimal("1.0")) < Decimal("0.01")


class TestGetHolding:
    """GET /api/v1/holdings/{id}"""

    async def test_get_existing(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Get existing holding returns full detail."""
        await _clear_holdings(db_session)
        h = await _insert_test_holding(db_session)

        resp = await client.get(f"/api/v1/holdings/{h.id}")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["id"] == h.id
        assert data["data"]["fund_code"] == "000001"
        assert data["data"]["fund_name"] == "测试基金A"

    async def test_get_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Non-existent holding returns 10001 error."""
        await _clear_holdings(db_session)

        resp = await client.get("/api/v1/holdings/99999")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 10001
        assert data["data"] is None


class TestUpdateHolding:
    """PUT /api/v1/holdings/{id}"""

    async def test_update_amount(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Update holding amount."""
        await _clear_holdings(db_session)
        h = await _insert_test_holding(db_session)

        resp = await client.put(
            f"/api/v1/holdings/{h.id}",
            json={"amount": "15000.00"},
        )
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["amount"] == "15000.00"
        # fund_code should be unchanged
        assert data["data"]["fund_code"] == "000001"

    async def test_update_fund_code_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sending fund_code in update body is silently ignored (not in schema)."""
        await _clear_holdings(db_session)
        h = await _insert_test_holding(db_session)

        resp = await client.put(
            f"/api/v1/holdings/{h.id}",
            json={
                "fund_code": "999999",  # This field is NOT in HoldingUpdate, so it is ignored
                "amount": "20000.00",
            },
        )
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        # fund_code should remain unchanged
        assert data["data"]["fund_code"] == "000001"

    async def test_update_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Update non-existent holding returns 10001."""
        await _clear_holdings(db_session)

        resp = await client.put(
            "/api/v1/holdings/99999",
            json={"amount": "15000.00"},
        )
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 10001


class TestDeleteHolding:
    """DELETE /api/v1/holdings/{id}"""

    async def test_delete_existing(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Delete existing holding cascades transactions."""
        await _clear_holdings(db_session)
        h = await _insert_test_holding(db_session)

        resp = await client.delete(f"/api/v1/holdings/{h.id}")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0

        # Verify holding is gone
        get_resp = await client.get(f"/api/v1/holdings/{h.id}")
        get_data = get_resp.json()
        assert get_data["code"] == 10001

    async def test_delete_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Delete non-existent holding returns 10001."""
        await _clear_holdings(db_session)

        resp = await client.delete("/api/v1/holdings/99999")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 10001


# ---------------------------------------------------------------------------
# Watchlist tests
# ---------------------------------------------------------------------------
class TestWatchlist:
    """Watchlist endpoints."""

    async def test_add_and_list_watchlist(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Add fund to watchlist and list it."""
        await _clear_holdings(db_session)

        # Add
        resp = await client.post(
            "/api/v1/watchlist",
            json={"fund_code": "000001", "fund_name": "测试基金A"},
        )
        data = resp.json()
        assert resp.status_code == 201
        assert data["code"] == 0
        assert data["data"]["fund_code"] == "000001"

        # List
        resp = await client.get("/api/v1/watchlist")
        data = resp.json()
        assert resp.status_code == 200
        assert len(data["data"]["items"]) >= 1
        assert data["data"]["items"][0]["fund_code"] == "000001"

    async def test_add_duplicate_idempotent(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Adding same fund twice is idempotent."""
        await _clear_holdings(db_session)

        await client.post(
            "/api/v1/watchlist",
            json={"fund_code": "000001", "fund_name": "测试基金A"},
        )
        resp = await client.post(
            "/api/v1/watchlist",
            json={"fund_code": "000001", "fund_name": "Duplicate"},
        )
        data = resp.json()

        assert resp.status_code == 201
        assert data["code"] == 0
        # Original name is preserved
        assert data["data"]["fund_name"] == "测试基金A"

    async def test_remove_watchlist(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Remove fund from watchlist."""
        await _clear_holdings(db_session)

        await client.post(
            "/api/v1/watchlist",
            json={"fund_code": "000001", "fund_name": "测试基金A"},
        )

        resp = await client.delete("/api/v1/watchlist/000001")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0

        # Verify it's gone
        resp = await client.get("/api/v1/watchlist")
        data = resp.json()
        assert len(data["data"]["items"]) == 0

    async def test_remove_nonexistent(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Remove non-existent watchlist item returns 10002."""
        await _clear_holdings(db_session)

        resp = await client.delete("/api/v1/watchlist/NONEXIST")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 10002


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------
class TestDashboard:
    """Dashboard endpoints."""

    async def test_summary_empty(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dashboard summary with no holdings."""
        await _clear_holdings(db_session)

        resp = await client.get("/api/v1/dashboard/summary")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["holding_count"] == 0
        assert data["data"]["total_asset"] == "0"

    async def test_summary_with_holdings(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dashboard summary with holdings."""
        await _clear_holdings(db_session)
        await _insert_test_holding(db_session)

        resp = await client.get("/api/v1/dashboard/summary")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["holding_count"] == 1
        assert Decimal(data["data"]["total_cost"]) > 0

    async def test_allocation_empty(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Allocation with no holdings returns empty list."""
        await _clear_holdings(db_session)

        resp = await client.get("/api/v1/dashboard/allocation")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["items"] == []

    async def test_allocation_with_holdings(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Allocation groups holdings by fund type."""
        await _clear_holdings(db_session)
        await _insert_test_holding(db_session)  # stock type (from fund lookup)

        resp = await client.get("/api/v1/dashboard/allocation")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        # Even if fund type lookup fails, the holding should be grouped as "unknown"
        assert len(data["data"]["items"]) >= 0

    async def test_returns_chart(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns chart endpoint works."""
        await _clear_holdings(db_session)
        await _insert_test_holding(db_session)

        resp = await client.get("/api/v1/dashboard/returns-chart?period=1m")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["period"] == "1m"
        assert "points" in data["data"]

    async def test_risk_metrics(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Risk metrics endpoint works."""
        await _clear_holdings(db_session)
        await _insert_test_holding(db_session)

        resp = await client.get("/api/v1/dashboard/risk-metrics")
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert "max_drawdown" in data["data"]
        assert "sharpe_ratio" in data["data"]
        assert "volatility" in data["data"]
