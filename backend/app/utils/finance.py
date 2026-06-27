"""
Financial calculation utilities — pure functions with no side effects.

All functions use ``Decimal`` for precision and are stateless.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from math import sqrt
from typing import Any


# ---------------------------------------------------------------------------
# Max drawdown
# ---------------------------------------------------------------------------
def calc_max_drawdown(nav_series: list[Decimal]) -> Decimal:
    """
    Calculate the maximum peak-to-trough decline.

    Returns the largest percentage drop from a preceding peak across the
    entire NAV series.  Returns ``Decimal("0")`` for empty or single-element
    series.
    """
    if len(nav_series) < 2:
        return Decimal("0")

    peak = nav_series[0]
    max_dd = Decimal("0")

    for nav in nav_series:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak if peak != 0 else Decimal("0")
        if dd > max_dd:
            max_dd = dd

    return max_dd


# ---------------------------------------------------------------------------
# Sharpe ratio
# ---------------------------------------------------------------------------
def calc_sharpe_ratio(
    daily_returns: list[Decimal],
    risk_free_rate: float = 0.03,
) -> float:
    """
    Calculate the annualised Sharpe ratio.

    Sharpe = (annualized_return - risk_free_rate) / annualized_volatility.

    Returns 0.0 when volatility is effectively zero (no meaningful returns).
    """
    if len(daily_returns) < 2:
        return 0.0

    float_returns = [float(r) for r in daily_returns]
    n = len(float_returns)

    # Average daily return
    avg_daily = sum(float_returns) / n

    # Annualize: multiply by 252 trading days
    annualized_return = avg_daily * 252.0

    # Annualized volatility
    ann_vol = calc_volatility(daily_returns)

    if ann_vol < 1e-12:
        return 0.0

    return (annualized_return - risk_free_rate) / ann_vol


# ---------------------------------------------------------------------------
# Volatility
# ---------------------------------------------------------------------------
def calc_volatility(daily_returns: list[Decimal]) -> float:
    """
    Calculate annualised volatility from daily returns.

    Uses population standard deviation of daily returns multiplied by
    sqrt(252) for annualisation.
    """
    if len(daily_returns) < 2:
        return 0.0

    float_returns = [float(r) for r in daily_returns]
    n = len(float_returns)

    mean = sum(float_returns) / n
    variance = sum((r - mean) ** 2 for r in float_returns) / (n - 1)

    daily_std = sqrt(variance)
    return daily_std * sqrt(252.0)


# ---------------------------------------------------------------------------
# Alpha & Beta (linear regression)
# ---------------------------------------------------------------------------
def calc_alpha_beta(
    fund_returns: list[Decimal],
    benchmark_returns: list[Decimal],
) -> tuple[float, float]:
    """
    Calculate Alpha and Beta via ordinary least-squares regression.

    Regresses fund daily returns (y) on benchmark daily returns (x):

        Beta = Cov(x, y) / Var(x)
        Alpha = mean(y) - Beta * mean(x)

    Annualised alpha = alpha_daily * 252.

    Returns (alpha: float, beta: float).  Returns (0.0, 1.0) when
    there are fewer than 2 data points or benchmark variance is zero.
    """
    if len(fund_returns) < 2 or len(benchmark_returns) < 2:
        return 0.0, 1.0
    if len(fund_returns) != len(benchmark_returns):
        raise ValueError(
            f"Length mismatch: fund_returns({len(fund_returns)}) vs "
            f"benchmark_returns({len(benchmark_returns)})"
        )

    n = len(fund_returns)
    y = [float(r) for r in fund_returns]
    x = [float(r) for r in benchmark_returns]

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Covariance and variance
    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((xi - mean_x) ** 2 for xi in x)

    if abs(var_x) < 1e-12:
        return 0.0, 1.0

    beta = cov / var_x
    alpha_daily = mean_y - beta * mean_x
    alpha_annual = alpha_daily * 252.0

    return alpha_annual, beta


# ---------------------------------------------------------------------------
# Cumulative return
# ---------------------------------------------------------------------------
def calc_cumulative_return(nav_series: list[Decimal]) -> Decimal:
    """
    Calculate cumulative return: (last_nav - first_nav) / first_nav.

    Returns Decimal("0") if the series is empty or first NAV is zero.
    """
    if len(nav_series) < 2:
        return Decimal("0")

    first = nav_series[0]
    last = nav_series[-1]

    if first == 0:
        return Decimal("0")

    return (last - first) / first


# ---------------------------------------------------------------------------
# Period returns
# ---------------------------------------------------------------------------
def _find_nav_at_offset(
    points: list[dict[str, Any]],
    target_date: date,
) -> Decimal | None:
    """
    Find the NAV closest to but not after *target_date*.

    Points must be sorted by date ascending.
    """
    best: dict[str, Any] | None = None
    for pt in points:
        pt_date = pt["date"]
        if isinstance(pt_date, str):
            pt_date = date.fromisoformat(pt_date)
        if pt_date <= target_date:
            best = pt
        else:
            break
    if best is not None:
        nav = best["nav"]
        return Decimal(str(nav)) if not isinstance(nav, Decimal) else nav
    return None


def calc_period_returns(
    nav_series: list[dict[str, Any]],
) -> dict[str, Decimal | None]:
    """
    Calculate period returns from a NAV series.

    *nav_series* must be a list of dicts with at least ``date`` and ``nav``
    keys, sorted by date ascending.

    Returns a dict with keys:
        daily, weekly, monthly, three_month, six_month,
        ytd, one_year, three_year, five_year.

    Each value is a Decimal return or None if insufficient history.
    """
    if not nav_series:
        return {
            "daily": None, "weekly": None, "monthly": None,
            "three_month": None, "six_month": None, "ytd": None,
            "one_year": None, "three_year": None, "five_year": None,
        }

    # Ensure sorted by date
    sorted_points = sorted(
        nav_series,
        key=lambda p: (
            date.fromisoformat(p["date"]) if isinstance(p["date"], str) else p["date"]
        ),
    )

    last_pt = sorted_points[-1]
    last_nav_raw = last_pt["nav"]
    last_nav = (
        Decimal(str(last_nav_raw))
        if not isinstance(last_nav_raw, Decimal)
        else last_nav_raw
    )
    last_date = last_pt["date"]
    if isinstance(last_date, str):
        last_date = date.fromisoformat(last_date)

    def _calc_return(offset_days: int) -> Decimal | None:
        target = last_date - timedelta(days=offset_days)
        prev_nav = _find_nav_at_offset(sorted_points, target)
        if prev_nav is None or prev_nav == 0:
            return None
        return (last_nav - prev_nav) / prev_nav

    # Daily return: use the end-point itself if only two points available;
    # prefer the point provided in the series.
    daily: Decimal | None = None
    if len(sorted_points) >= 2:
        prev = sorted_points[-2]
        prev_nav_raw = prev["nav"]
        prev_nav = (
            Decimal(str(prev_nav_raw))
            if not isinstance(prev_nav_raw, Decimal)
            else prev_nav_raw
        )
        if prev_nav != 0:
            daily = (last_nav - prev_nav) / prev_nav

    # YTD: from Jan 1 of current year
    ytd: Decimal | None = None
    ytd_start = date(last_date.year, 1, 1)
    if ytd_start < last_date:
        ytd_nav = _find_nav_at_offset(sorted_points, ytd_start)
        if ytd_nav is not None and ytd_nav != 0:
            ytd = (last_nav - ytd_nav) / ytd_nav

    return {
        "daily": daily,
        "weekly": _calc_return(7),
        "monthly": _calc_return(30),
        "three_month": _calc_return(91),
        "six_month": _calc_return(182),
        "ytd": ytd,
        "one_year": _calc_return(365),
        "three_year": _calc_return(1095),
        "five_year": _calc_return(1825),
    }


# ---------------------------------------------------------------------------
# Weighted portfolio return
# ---------------------------------------------------------------------------
def weighted_portfolio_return(
    holdings_returns: list[tuple[Decimal, Decimal]],
) -> Decimal:
    """
    Calculate weighted portfolio return.

    Each tuple is (weight, return) where both are Decimal values.

    Returns sum(weight_i * return_i) for each holding.
    """
    total = Decimal("0")
    for weight, ret in holdings_returns:
        total += weight * ret
    return total
