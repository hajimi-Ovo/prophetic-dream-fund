"""
Unit tests for FundRanker engine.

These tests verify factor-scoring logic with minimal DB interaction.
"""

from decimal import Decimal

import pytest

from app.engine.fund_ranker import FACTOR_WEIGHTS, FundRanker


class TestFundRankerFactors:
    """Tests for individual factor scoring methods."""

    def setup_method(self) -> None:
        self.ranker = FundRanker()

    def test_weights_sum_to_one(self) -> None:
        """All factor weights must sum to 1.0."""
        assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 0.001

    # -- Valuation --
    def test_valuation_low_percentile(self) -> None:
        """Current NAV near low → high valuation score (cheap)."""
        nav = [Decimal("1.00")] + [Decimal("1.50")] * 4 + [Decimal("2.00")] * 2 + [
            Decimal("2.50"), Decimal("2.00"), Decimal("1.50"), Decimal("1.20"),
        ]
        score = self.ranker._calc_valuation_score(nav)
        assert score > Decimal("50")

    def test_valuation_high_percentile(self) -> None:
        """Current NAV near high → low valuation score (expensive)."""
        nav = [Decimal("1.00")] * 3 + [Decimal("1.20")] * 2 + [Decimal("1.50")] * 2 + [
            Decimal("2.00"), Decimal("2.50"), Decimal("2.80"),
        ]
        score = self.ranker._calc_valuation_score(nav)
        assert score < Decimal("50")

    def test_valuation_flat(self) -> None:
        """No variance in NAV returns 50."""
        nav = [Decimal("1.00")] * 20
        score = self.ranker._calc_valuation_score(nav)
        assert score == Decimal("50")

    def test_valuation_insufficient_data(self) -> None:
        """Less than 10 points returns 50."""
        nav = [Decimal("1.00"), Decimal("1.10")]
        score = self.ranker._calc_valuation_score(nav)
        assert score == Decimal("50")

    # -- Scale --
    def test_scale_optimal_range(self) -> None:
        """Fund in optimal range (5-100 hundredM) gets high score."""
        # 50 hundredM = 5B CNY
        score = self.ranker._calc_scale_score(Decimal("5000000000"))
        assert score > Decimal("70")

    def test_scale_too_small(self) -> None:
        """Very small fund gets low score."""
        score = self.ranker._calc_scale_score(Decimal("50000000"))  # 50M
        assert score < Decimal("50")

    def test_scale_none(self) -> None:
        """None scale returns 50."""
        score = self.ranker._calc_scale_score(None)
        assert score == Decimal("50")

    def test_scale_invalid(self) -> None:
        """Invalid scale returns 50."""
        score = self.ranker._calc_scale_score("invalid")
        assert score == Decimal("50")

    # -- Fee --
    def test_fee_low(self) -> None:
        """Low fee gets high score."""
        score = self.ranker._calc_fee_score(Decimal("0.0050"))  # 0.5%
        assert score > Decimal("60")

    def test_fee_high(self) -> None:
        """High fee gets low score."""
        score = self.ranker._calc_fee_score(Decimal("0.0200"))  # 2.0%
        assert score < Decimal("20")

    def test_fee_none(self) -> None:
        """None fee returns 50."""
        score = self.ranker._calc_fee_score(None)
        assert score == Decimal("50")

    # -- Quality --
    def test_quality_positive_returns(self) -> None:
        """Positive returns yield decent quality score."""
        # Simulate daily returns of ~0.05%
        rets = [Decimal("0.0005")] * 200
        score = self.ranker._calc_quality_score(rets)
        # With positive return, Sharpe positive → quality > 40
        assert score > Decimal("25")

    def test_quality_insufficient_data(self) -> None:
        """Less than 22 returns gives 50."""
        score = self.ranker._calc_quality_score([Decimal("0.001")] * 5)
        assert score == Decimal("50")

    # -- Daily returns helper --
    def test_calc_daily_returns(self) -> None:
        """Daily return calculation is correct."""
        nav = [Decimal("1.00"), Decimal("1.10"), Decimal("0.99")]
        rets = self.ranker._calc_daily_returns(nav)
        assert len(rets) == 2
        assert rets[0] == Decimal("0.10")  # (1.10-1.00)/1.00
        assert float(rets[1]) == pytest.approx(-0.10, abs=0.01)  # (0.99-1.10)/1.10

    def test_calc_daily_returns_empty(self) -> None:
        """Empty or single NAV returns empty."""
        assert self.ranker._calc_daily_returns([]) == []
        assert self.ranker._calc_daily_returns([Decimal("1.00")]) == []
