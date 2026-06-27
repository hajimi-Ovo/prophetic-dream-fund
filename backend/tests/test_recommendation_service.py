"""
Integration tests for RecommendationService.

Requires test database with fund data for full-flow testing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundManager, FundNav
from app.models.recommendation import RecommendationLog, RiskProfile
from app.services.recommendation_service import RecommendationService


async def _insert_test_funds(db: AsyncSession) -> None:
    """Insert test fund data for recommendation tests."""
    funds = [
        Fund(code="R001", name="推荐测试股票基金A", type="stock",
             scale=Decimal("3000000000"), fee_rate=Decimal("0.0150"),
             company="测试公司A", inception_date=date(2020, 1, 1)),
        Fund(code="R002", name="推荐测试债券基金B", type="bond",
             scale=Decimal("8000000000"), fee_rate=Decimal("0.0060"),
             company="测试公司B", inception_date=date(2019, 6, 1)),
        Fund(code="R003", name="推荐测试混合基金C", type="mixed",
             scale=Decimal("5000000000"), fee_rate=Decimal("0.0120"),
             company="测试公司C", inception_date=date(2021, 3, 15)),
        Fund(code="R004", name="推荐测试货币基金D", type="money",
             scale=Decimal("20000000000"), fee_rate=Decimal("0.0025"),
             company="测试公司D", inception_date=date(2018, 1, 1)),
    ]
    db.add_all(funds)
    await db.flush()

    # Add NAV history for each fund (60 days of rising NAV)
    for code, base in [("R001", Decimal("1.0000")), ("R002", Decimal("2.0000")),
                       ("R003", Decimal("1.5000")), ("R004", Decimal("1.0000"))]:
        navs = []
        for i in range(60):
            d = date(2025, 4, 1) + __import__("datetime").timedelta(days=i)
            nav = base + Decimal(str(i * base * Decimal("0.001")))
            navs.append(FundNav(
                fund_code=code, date=d, nav=nav,
                daily_return=Decimal("0.001") if i > 0 else None,
            ))
        db.add_all(navs)
    await db.flush()

    # Add manager for stock fund
    db.add(FundManager(
        fund_code="R001", name="李明",
        start_date=date(2020, 6, 1),
        tenure_return=Decimal("0.4500"),
    ))
    await db.flush()


async def _clear_recommendation_tables(db: AsyncSession) -> None:
    """Clear recommendation-related tables."""
    for model in (RecommendationLog, RiskProfile, FundNav, FundManager, Fund):
        await db.execute(delete(model))
    await db.flush()


class TestRiskAssessment:
    """Tests for risk profile save/get."""

    async def test_save_new_profile(self, db_session: AsyncSession) -> None:
        """Save a new risk profile."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        result = await service.save_risk_assessment({
            "risk_tolerance": "moderate",
            "investment_horizon": "long",
            "return_expectation": "balanced",
        }, user_id=1)

        assert result["risk_level"] == "moderate"
        assert "suggested_allocation" in result
        assert result["user_id"] == 1

    async def test_save_update_existing(self, db_session: AsyncSession) -> None:
        """Update existing profile."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        # Save first
        await service.save_risk_assessment({
            "risk_tolerance": "conservative",
            "investment_horizon": "short",
            "return_expectation": "conservative",
        }, user_id=1)

        # Update
        result = await service.save_risk_assessment({
            "risk_tolerance": "aggressive",
            "investment_horizon": "long",
            "return_expectation": "aggressive",
        }, user_id=1)

        assert result["risk_level"] == "aggressive"

    async def test_get_existing_profile(self, db_session: AsyncSession) -> None:
        """Get an existing risk profile."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        await service.save_risk_assessment({
            "risk_tolerance": "aggressive",
            "investment_horizon": "very_long",
            "return_expectation": "aggressive",
        }, user_id=99)

        result = await service.get_risk_assessment(user_id=99)
        assert result is not None
        assert result["risk_level"] == "aggressive"

    async def test_get_nonexistent_profile(self, db_session: AsyncSession) -> None:
        """Non-existent profile returns None."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        result = await service.get_risk_assessment(user_id=99999)
        assert result is None


class TestRecommendedFunds:
    """Tests for fund recommendation pipeline."""

    async def test_get_recommended_funds(self, db_session: AsyncSession) -> None:
        """Get ranked fund recommendations with test data."""
        await _clear_recommendation_tables(db_session)
        await _insert_test_funds(db_session)
        service = RecommendationService(db_session)

        result = await service.get_recommended_funds(
            {"risk_tolerance": "moderate"}, strategy="hybrid", limit=5
        )

        assert "items" in result
        assert "strategy" in result
        assert result["strategy"] == "hybrid"
        assert len(result["items"]) > 0
        # Each item should have required fields
        item = result["items"][0]
        assert "fund_code" in item
        assert "fund_name" in item
        assert "score" in item
        assert "reasons" in item
        assert "risk_match" in item
        assert "suggested_action" in item

    async def test_recommended_funds_sorted_by_score(self, db_session: AsyncSession) -> None:
        """Recommendations are sorted descending by score."""
        await _clear_recommendation_tables(db_session)
        await _insert_test_funds(db_session)
        service = RecommendationService(db_session)

        result = await service.get_recommended_funds(
            {"risk_tolerance": "moderate"}, limit=10
        )
        items = result["items"]
        if len(items) >= 2:
            for i in range(len(items) - 1):
                assert float(items[i]["score"]) >= float(items[i + 1]["score"])


class TestAmountAdvice:
    """Tests for amount advice."""

    async def test_conservative_amount(self, db_session: AsyncSession) -> None:
        """Conservative risk gets smaller suggested amount."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        result = await service.get_amount_advice({
            "risk_tolerance": "conservative",
            "investment_horizon": "short",
        })
        assert result["suggested_amount"] <= Decimal("5000")

    async def test_aggressive_amount(self, db_session: AsyncSession) -> None:
        """Aggressive risk gets larger suggested amount."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        result = await service.get_amount_advice({
            "risk_tolerance": "aggressive",
            "investment_horizon": "very_long",
        })
        assert result["suggested_amount"] > Decimal("10000")


class TestPortfolioPlan:
    """Tests for portfolio plan building."""

    async def test_portfolio_with_funds(self, db_session: AsyncSession) -> None:
        """Build portfolio with real fund data."""
        await _clear_recommendation_tables(db_session)
        await _insert_test_funds(db_session)
        service = RecommendationService(db_session)

        result = await service.get_portfolio_plan(
            {"risk_tolerance": "moderate"}, total_amount=Decimal("50000")
        )

        assert "total_amount" in result
        assert "allocations" in result
        assert "expected_return" in result
        assert "expected_risk" in result
        assert "rebalance_suggestions" in result

    async def test_portfolio_empty_db(self, db_session: AsyncSession) -> None:
        """Empty DB returns empty allocations."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        result = await service.get_portfolio_plan(
            {"risk_tolerance": "conservative"}, total_amount=Decimal("10000")
        )
        assert result["total_amount"] == Decimal("10000")
        assert result["allocations"] == []


class TestBacktest:
    """Tests for backtesting."""

    async def test_backtest_empty(self, db_session: AsyncSession) -> None:
        """Backtest with no data returns empty result."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        result = await service.get_backtest(strategy="hybrid", period="1y")
        assert result["strategy"] == "hybrid"
        assert result["period"] == "1y"
        assert "start_date" in result
        assert "end_date" in result

    async def test_backtest_with_data(self, db_session: AsyncSession) -> None:
        """Backtest with fund NAV data."""
        await _clear_recommendation_tables(db_session)
        await _insert_test_funds(db_session)
        service = RecommendationService(db_session)

        result = await service.get_backtest(strategy="hybrid", period="1y")
        assert result["strategy"] == "hybrid"
        assert "total_return" in result
        assert "sharpe_ratio" in result


class TestTimingAdvice:
    """Tests for timing advice."""

    async def test_timing_nonexistent_fund(self, db_session: AsyncSession) -> None:
        """Timing for non-existent fund."""
        await _clear_recommendation_tables(db_session)
        service = RecommendationService(db_session)

        result = await service.get_timing_advice("NONEXIST")
        assert result["signal"] == "hold"
        assert "Fund not found" in result["reasons"][0]

    async def test_timing_with_data(self, db_session: AsyncSession) -> None:
        """Timing with NAV data."""
        await _clear_recommendation_tables(db_session)
        await _insert_test_funds(db_session)
        service = RecommendationService(db_session)

        result = await service.get_timing_advice("R001")
        assert result["fund_code"] == "R001"
        assert "valuation_percentile" in result
        assert "signal" in result
        assert "trend_signal" in result
        assert len(result["reasons"]) > 0
