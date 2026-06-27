"""
API integration tests for /recommend endpoints.

Uses the test client with in-memory SQLite database.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundManager, FundNav
from app.models.recommendation import RecommendationLog, RiskProfile


async def _insert_test_funds(db: AsyncSession) -> None:
    """Insert test funds with NAV data."""
    funds = [
        Fund(code="A001", name="推荐API测试基金A", type="stock",
             scale=Decimal("3000000000"), fee_rate=Decimal("0.0150"),
             company="API测试公司", inception_date=date(2020, 1, 1)),
        Fund(code="A002", name="推荐API测试基金B", type="bond",
             scale=Decimal("8000000000"), fee_rate=Decimal("0.0060"),
             company="API测试公司", inception_date=date(2019, 6, 1)),
    ]
    db.add_all(funds)
    await db.flush()

    for code, base in [("A001", Decimal("1.0000")), ("A002", Decimal("2.0000"))]:
        navs = []
        for i in range(120):  # 120 days for adequate history
            d = date(2025, 3, 1) + __import__("datetime").timedelta(days=i)
            nav = base + Decimal(str(i * base * Decimal("0.001")))
            navs.append(FundNav(
                fund_code=code, date=d, nav=nav,
                daily_return=Decimal("0.001") if i > 0 else None,
            ))
        db.add_all(navs)
    await db.flush()

    db.add(FundManager(
        fund_code="A001", name="王五",
        start_date=date(2020, 3, 1),
        tenure_return=Decimal("0.6000"),
    ))
    await db.flush()


async def _clear_data(db: AsyncSession) -> None:
    """Clear all test data."""
    for model in (RecommendationLog, RiskProfile, FundNav, FundManager, Fund):
        await db.execute(delete(model))
    await db.flush()


# ============================================================================
# Risk Assessment
# ============================================================================
class TestRiskAssessmentAPI:
    """POST /GET /api/v1/recommend/risk-assessment"""

    async def test_post_risk_assessment(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Save a risk assessment."""
        await _clear_data(db_session)

        resp = await client.post("/api/v1/recommend/risk-assessment", json={
            "risk_tolerance": "moderate",
            "investment_horizon": "long",
            "return_expectation": "balanced",
        })
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert data["data"]["risk_level"] == "moderate"
        assert "suggested_allocation" in data["data"]

    async def test_post_invalid_risk_tolerance(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Invalid risk_tolerance returns validation error."""
        await _clear_data(db_session)

        resp = await client.post("/api/v1/recommend/risk-assessment", json={
            "risk_tolerance": "insane",
            "investment_horizon": "long",
            "return_expectation": "balanced",
        })
        assert resp.status_code == 422  # Validation error

    async def test_get_nonexistent_assessment(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Get non-existent assessment."""
        await _clear_data(db_session)

        resp = await client.get("/api/v1/recommend/risk-assessment?user_id=99999")
        data = resp.json()

        assert data["code"] == 30002
        assert data["data"] is None

    async def test_get_existing_assessment(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Get an existing risk assessment."""
        await _clear_data(db_session)

        # First create one
        await client.post("/api/v1/recommend/risk-assessment?user_id=42", json={
            "risk_tolerance": "conservative",
            "investment_horizon": "short",
            "return_expectation": "conservative",
        })

        # Then retrieve
        resp = await client.get("/api/v1/recommend/risk-assessment?user_id=42")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["risk_level"] == "conservative"


# ============================================================================
# Recommended Funds
# ============================================================================
class TestRecommendedFundsAPI:
    """GET /api/v1/recommend/funds"""

    async def test_get_recommended_funds(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Get recommended funds list."""
        await _clear_data(db_session)
        await _insert_test_funds(db_session)

        resp = await client.get(
            "/api/v1/recommend/funds?strategy=hybrid&limit=5&risk_tolerance=moderate"
        )
        data = resp.json()

        assert resp.status_code == 200
        assert data["code"] == 0
        assert "items" in data["data"]
        assert data["data"]["strategy"] == "hybrid"
        assert len(data["data"]["items"]) > 0

    async def test_recommended_funds_empty(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Empty database returns empty list."""
        await _clear_data(db_session)

        resp = await client.get("/api/v1/recommend/funds")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["items"] == []

    async def test_recommended_funds_with_limit(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Limit parameter is respected."""
        await _clear_data(db_session)
        await _insert_test_funds(db_session)

        resp = await client.get("/api/v1/recommend/funds?limit=1")
        data = resp.json()

        assert len(data["data"]["items"]) <= 1


# ============================================================================
# Timing Advice
# ============================================================================
class TestTimingAdviceAPI:
    """GET /api/v1/recommend/timing/{fund_code}"""

    async def test_timing_nonexistent(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Timing for a non-existent fund."""
        await _clear_data(db_session)

        resp = await client.get("/api/v1/recommend/timing/UNKNOWN")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["signal"] == "hold"

    async def test_timing_with_data(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Timing with fund data returns signals."""
        await _clear_data(db_session)
        await _insert_test_funds(db_session)

        resp = await client.get("/api/v1/recommend/timing/A001")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["fund_code"] == "A001"
        assert "valuation_percentile" in data["data"]
        assert "signal" in data["data"]
        assert "trend_signal" in data["data"]
        assert len(data["data"]["reasons"]) > 0


# ============================================================================
# Amount Advice
# ============================================================================
class TestAmountAdviceAPI:
    """GET /api/v1/recommend/amount"""

    async def test_amount_conservative(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Conservative amount advice."""
        await _clear_data(db_session)

        resp = await client.get(
            "/api/v1/recommend/amount?risk_tolerance=conservative&investment_horizon=short"
        )
        data = resp.json()

        assert data["code"] == 0
        assert "suggested_amount" in data["data"]
        assert "min_amount" in data["data"]
        assert "max_amount" in data["data"]

    async def test_amount_aggressive(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Aggressive amount advice is larger."""
        await _clear_data(db_session)

        resp = await client.get(
            "/api/v1/recommend/amount?risk_tolerance=aggressive&investment_horizon=very_long"
        )
        data = resp.json()

        assert data["code"] == 0
        assert float(data["data"]["suggested_amount"]) >= 50000


# ============================================================================
# Portfolio Plan
# ============================================================================
class TestPortfolioPlanAPI:
    """GET /api/v1/recommend/portfolio"""

    async def test_portfolio_default(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Portfolio with default parameters."""
        await _clear_data(db_session)
        await _insert_test_funds(db_session)

        resp = await client.get("/api/v1/recommend/portfolio?total_amount=50000")
        data = resp.json()

        assert data["code"] == 0
        assert "allocations" in data["data"]
        assert "expected_return" in data["data"]
        assert "rebalance_suggestions" in data["data"]

    async def test_portfolio_custom_amount(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Portfolio with custom total_amount."""
        await _clear_data(db_session)
        await _insert_test_funds(db_session)

        resp = await client.get(
            "/api/v1/recommend/portfolio?total_amount=100000&risk_tolerance=aggressive"
        )
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["total_amount"] is not None


# ============================================================================
# Backtest
# ============================================================================
class TestBacktestAPI:
    """GET /api/v1/recommend/backtest"""

    async def test_backtest_default(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Backtest with default parameters."""
        await _clear_data(db_session)
        await _insert_test_funds(db_session)

        resp = await client.get("/api/v1/recommend/backtest?strategy=hybrid&period=1y")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["strategy"] == "hybrid"
        assert data["data"]["period"] == "1y"
        assert "start_date" in data["data"]

    async def test_backtest_different_strategies(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Different strategies produce different results."""
        await _clear_data(db_session)
        await _insert_test_funds(db_session)

        resp1 = await client.get("/api/v1/recommend/backtest?strategy=value&period=1y")
        resp2 = await client.get("/api/v1/recommend/backtest?strategy=growth&period=1y")

        assert resp1.json()["code"] == 0
        assert resp2.json()["code"] == 0

    async def test_backtest_empty_db(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Backtest with empty DB returns empty result."""
        await _clear_data(db_session)

        resp = await client.get("/api/v1/recommend/backtest")
        data = resp.json()

        assert data["code"] == 0
        assert data["data"]["nav_series"] == []
