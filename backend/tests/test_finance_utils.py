"""
Unit tests for app.utils.finance — pure financial calculation functions.

All functions are stateless; no mocking required.
"""

from decimal import Decimal

import pytest

from app.utils.finance import (
    calc_alpha_beta,
    calc_cumulative_return,
    calc_max_drawdown,
    calc_period_returns,
    calc_sharpe_ratio,
    calc_volatility,
    weighted_portfolio_return,
)


# ---------------------------------------------------------------------------
# calc_max_drawdown
# ---------------------------------------------------------------------------
class TestMaxDrawdown:
    """Tests for maximum drawdown calculation."""

    def test_normal_case(self) -> None:
        """Typical peak-to-trough scenario."""
        nav = [
            Decimal("1.00"),
            Decimal("1.10"),  # peak
            Decimal("1.05"),
            Decimal("0.90"),  # trough — DD = (1.10-0.90)/1.10 = 0.1818...
            Decimal("1.00"),
        ]
        result = calc_max_drawdown(nav)
        expected = (Decimal("1.10") - Decimal("0.90")) / Decimal("1.10")
        assert abs(result - expected) < Decimal("0.001")

    def test_always_rising(self) -> None:
        """No drawdown when NAV always increases."""
        nav = [
            Decimal("1.00"),
            Decimal("1.05"),
            Decimal("1.10"),
            Decimal("1.15"),
        ]
        result = calc_max_drawdown(nav)
        assert result == Decimal("0")

    def test_single_element(self) -> None:
        """Single-element series returns zero drawdown."""
        assert calc_max_drawdown([Decimal("1.00")]) == Decimal("0")

    def test_empty(self) -> None:
        """Empty series returns zero."""
        assert calc_max_drawdown([]) == Decimal("0")

    def test_multiple_peaks(self) -> None:
        """Largest drawdown may occur after a later peak."""
        nav = [
            Decimal("1.00"),
            Decimal("1.50"),  # peak 1
            Decimal("1.40"),
            Decimal("1.20"),  # DD from peak1 = 0.20
            Decimal("2.00"),  # peak 2
            Decimal("1.00"),  # DD from peak2 = 0.50 (larger)
        ]
        result = calc_max_drawdown(nav)
        expected = (Decimal("2.00") - Decimal("1.00")) / Decimal("2.00")
        assert abs(result - expected) < Decimal("0.001")


# ---------------------------------------------------------------------------
# calc_sharpe_ratio
# ---------------------------------------------------------------------------
class TestSharpeRatio:
    """Tests for Sharpe ratio."""

    def test_positive_returns(self) -> None:
        """Mostly positive daily returns yield positive Sharpe."""
        # Mix of returns to create non-zero volatility
        returns = [Decimal("0.0015") if i % 2 == 0 else Decimal("0.0005")
                   for i in range(252)]
        sr = calc_sharpe_ratio(returns, risk_free_rate=0.03)
        assert sr > 0

    def test_no_variance(self) -> None:
        """Zero variance returns zero Sharpe."""
        returns = [Decimal("0")] * 100
        assert calc_sharpe_ratio(returns) == 0.0

    def test_insufficient_data(self) -> None:
        """Less than 2 points returns zero."""
        assert calc_sharpe_ratio([Decimal("0.01")]) == 0.0

    def test_negative_returns(self) -> None:
        """Negative returns produce negative Sharpe."""
        returns = [Decimal("-0.0025") if i % 2 == 0 else Decimal("-0.0015")
                   for i in range(252)]
        sr = calc_sharpe_ratio(returns, risk_free_rate=0.03)
        assert sr < 0


# ---------------------------------------------------------------------------
# calc_volatility
# ---------------------------------------------------------------------------
class TestVolatility:
    """Tests for annualized volatility."""

    def test_constant_returns(self) -> None:
        """Constant returns have (near) zero volatility."""
        returns = [Decimal("0.001")] * 100
        assert calc_volatility(returns) == pytest.approx(0.0, abs=1e-12)

    def test_varying_returns(self) -> None:
        """Varying returns produce positive volatility."""
        returns = [
            Decimal("0.01"), Decimal("-0.01"),
            Decimal("0.02"), Decimal("-0.005"),
            Decimal("0.001"),
        ] * 20
        vol = calc_volatility(returns)
        assert vol > 0

    def test_insufficient_data(self) -> None:
        """Less than 2 points returns zero."""
        assert calc_volatility([Decimal("0.01")]) == 0.0


# ---------------------------------------------------------------------------
# calc_alpha_beta
# ---------------------------------------------------------------------------
class TestAlphaBeta:
    """Tests for alpha and beta via linear regression."""

    def test_perfect_correlation(self) -> None:
        """When fund = benchmark, beta=1, alpha=0."""
        returns = [Decimal("0.001")] * 100
        alpha, beta = calc_alpha_beta(returns, returns)
        assert abs(beta - 1.0) < 0.001
        assert abs(alpha - 0.0) < 0.001

    def test_length_mismatch(self) -> None:
        """Raises ValueError when lengths differ."""
        with pytest.raises(ValueError):
            calc_alpha_beta(
                [Decimal("0.01")] * 10,
                [Decimal("0.01")] * 5,
            )

    def test_insufficient_data(self) -> None:
        """Less than 2 points returns defaults."""
        alpha, beta = calc_alpha_beta(
            [Decimal("0.01")],
            [Decimal("0.01")],
        )
        assert alpha == 0.0
        assert beta == 1.0

    def test_no_benchmark_variance(self) -> None:
        """Constant benchmark returns (no variance) yields defaults."""
        fund = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")]
        bench = [Decimal("0"), Decimal("0"), Decimal("0")]
        alpha, beta = calc_alpha_beta(fund, bench)
        assert alpha == 0.0
        assert beta == 1.0


# ---------------------------------------------------------------------------
# calc_cumulative_return
# ---------------------------------------------------------------------------
class TestCumulativeReturn:
    """Tests for cumulative return."""

    def test_normal(self) -> None:
        """Standard growth calculation."""
        nav = [Decimal("1.00"), Decimal("1.20")]
        assert calc_cumulative_return(nav) == Decimal("0.20")

    def test_loss(self) -> None:
        """Negative cumulative return."""
        nav = [Decimal("1.00"), Decimal("0.80")]
        assert calc_cumulative_return(nav) == Decimal("-0.20")

    def test_single_element(self) -> None:
        """Single-element series returns zero."""
        assert calc_cumulative_return([Decimal("1.00")]) == Decimal("0")

    def test_zero_start(self) -> None:
        """Zero first NAV returns zero."""
        nav = [Decimal("0"), Decimal("1.00")]
        assert calc_cumulative_return(nav) == Decimal("0")

    def test_long_series(self) -> None:
        """Multi-point series."""
        nav = [
            Decimal("2.00"),
            Decimal("2.10"),
            Decimal("2.05"),
            Decimal("2.40"),
        ]
        expected = (Decimal("2.40") - Decimal("2.00")) / Decimal("2.00")
        assert calc_cumulative_return(nav) == expected


# ---------------------------------------------------------------------------
# calc_period_returns
# ---------------------------------------------------------------------------
class TestPeriodReturns:
    """Tests for period return calculations."""

    def test_daily_return(self) -> None:
        """Two consecutive days should produce a daily return."""
        from datetime import date

        nav = [
            {"date": date(2025, 6, 1), "nav": Decimal("1.00")},
            {"date": date(2025, 6, 2), "nav": Decimal("1.01")},
        ]
        result = calc_period_returns(nav)
        assert result["daily"] == Decimal("0.01")

    def test_empty(self) -> None:
        """Empty series returns all None."""
        result = calc_period_returns([])
        for v in result.values():
            assert v is None

    def test_ytd(self) -> None:
        """YTD from Jan 1."""
        from datetime import date

        nav = [
            {"date": date(2024, 12, 31), "nav": Decimal("0.98")},
            {"date": date(2025, 1, 2), "nav": Decimal("1.00")},
            {"date": date(2025, 3, 15), "nav": Decimal("1.05")},
        ]
        result = calc_period_returns(nav)
        # YTD boundary is Jan 1; closest point <= Jan 1 is Dec 31 (0.98)
        # Return = (1.05 - 0.98) / 0.98 = 0.071428...
        assert result["ytd"] is not None
        assert abs(float(result["ytd"]) - 0.0714) < 0.001  # type: ignore[arg-type]

    def test_with_string_dates(self) -> None:
        """String date inputs are handled."""
        nav = [
            {"date": "2025-06-01", "nav": "1.00"},
            {"date": "2025-06-02", "nav": "1.02"},
        ]
        result = calc_period_returns(nav)
        assert result["daily"] is not None
        assert float(result["daily"]) == 0.02  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# weighted_portfolio_return
# ---------------------------------------------------------------------------
class TestWeightedPortfolioReturn:
    """Tests for weighted portfolio return."""

    def test_basic(self) -> None:
        """Sum of weight * return."""
        holdings = [
            (Decimal("0.5"), Decimal("0.10")),
            (Decimal("0.3"), Decimal("0.05")),
            (Decimal("0.2"), Decimal("-0.02")),
        ]
        expected = (
            Decimal("0.5") * Decimal("0.10")
            + Decimal("0.3") * Decimal("0.05")
            + Decimal("0.2") * Decimal("-0.02")
        )
        result = weighted_portfolio_return(holdings)
        assert result == expected

    def test_empty(self) -> None:
        """Empty holdings returns zero."""
        assert weighted_portfolio_return([]) == Decimal("0")

    def test_full_weight(self) -> None:
        """Single holding with full weight."""
        holdings = [(Decimal("1.0"), Decimal("0.12"))]
        assert weighted_portfolio_return(holdings) == Decimal("0.12")
