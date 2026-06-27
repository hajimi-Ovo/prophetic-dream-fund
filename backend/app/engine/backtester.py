"""
Historical backtesting engine — simulates portfolio performance over
a specified lookback period with monthly rebalancing and friction costs.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundNav
from app.utils.finance import calc_max_drawdown, calc_sharpe_ratio

logger = logging.getLogger(__name__)

# Friction cost as a fraction per rebalance trade
FRICTION_RATE = Decimal("0.0015")  # 0.15%

# Strategy weights
STRATEGY_WEIGHTS: dict[str, dict[str, Decimal]] = {
    "hybrid": {
        "stock": Decimal("0.35"),
        "bond": Decimal("0.40"),
        "money": Decimal("0.15"),
        "mixed": Decimal("0.10"),
    },
    "value": {
        "stock": Decimal("0.25"),
        "bond": Decimal("0.50"),
        "money": Decimal("0.15"),
        "mixed": Decimal("0.10"),
    },
    "growth": {
        "stock": Decimal("0.55"),
        "bond": Decimal("0.10"),
        "money": Decimal("0.05"),
        "mixed": Decimal("0.30"),
    },
}


class Backtester:
    """Async historical backtest simulator."""

    async def run(
        self,
        strategy: str,
        period: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Run a backtest for *strategy* over *period*.

        *strategy*: hybrid, value, growth
        *period*: 1y, 3y, 5y

        Returns a dict with NAV series, benchmark series, and key metrics.
        """
        period_days = {"1y": 365, "3y": 1095, "5y": 1825}.get(period, 365)
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        weights = STRATEGY_WEIGHTS.get(strategy, STRATEGY_WEIGHTS["hybrid"])

        # 1. Select representative funds for each type
        strategy_funds = await self._select_strategy_funds(db, weights)

        if not strategy_funds:
            return self._empty_result(strategy, period, start_date, end_date)

        # 2. Build monthly NAV series for portfolio and benchmark
        portfolio_nav, benchmark_nav = await self._simulate_nav_series(
            db, strategy_funds, weights, start_date, end_date
        )

        # 3. Calculate metrics
        metrics = self._calc_metrics(portfolio_nav)

        return {
            "strategy": strategy,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "total_return": metrics["total_return"],
            "annual_return": metrics["annual_return"],
            "max_drawdown": metrics["max_drawdown"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "win_rate": metrics["win_rate"],
            "nav_series": portfolio_nav,
            "benchmark_series": benchmark_nav,
        }

    # ------------------------------------------------------------------
    # Strategy fund selection
    # ------------------------------------------------------------------
    async def _select_strategy_funds(
        self, db: AsyncSession, weights: dict[str, Decimal]
    ) -> dict[str, list[dict[str, Any]]]:
        """Select top funds for each type based on recent returns."""
        result: dict[str, list[dict[str, Any]]] = {}

        for fund_type in weights:
            q = (
                select(Fund)
                .where(Fund.type.like(f"%{fund_type}%"))
                .limit(5)
            )
            rows = (await db.execute(q)).scalars().all()

            fund_dicts: list[dict[str, Any]] = []
            for f in rows:
                nav_pts = await self._get_nav_points(db, f.code, limit=260)
                nav_vals = [Decimal(str(p["nav"])) for p in nav_pts if p.get("nav")]

                daily_rets: list[Decimal] = []
                for i in range(1, len(nav_vals)):
                    if nav_vals[i - 1] != 0:
                        daily_rets.append(
                            (nav_vals[i] - nav_vals[i - 1]) / nav_vals[i - 1]
                        )

                fund_dicts.append({
                    "code": f.code,
                    "name": f.name,
                    "type": f.type,
                    "nav_values": nav_vals,
                    "daily_returns": daily_rets,
                })

            # Sort by recent return
            fund_dicts.sort(
                key=lambda x: (
                    float(sum(x["daily_returns"][-63:]) / max(len(x["daily_returns"][-63:]), 1))
                    if x["daily_returns"]
                    else 0
                ),
                reverse=True,
            )

            result[fund_type] = fund_dicts[:2]  # Top 2 per type

        return result

    # ------------------------------------------------------------------
    # NAV series simulation
    # ------------------------------------------------------------------
    async def _simulate_nav_series(
        self,
        db: AsyncSession,
        strategy_funds: dict[str, list[dict[str, Any]]],
        weights: dict[str, Decimal],
        start_date: date,
        end_date: date,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Simulate portfolio and benchmark NAV over the period."""
        # Get all fund codes
        all_codes: list[str] = []
        type_weight_map: dict[str, Decimal] = {}
        for ft, funds in strategy_funds.items():
            type_w = weights.get(ft, Decimal("0"))
            per_fund_w = type_w / Decimal(str(max(len(funds), 1)))
            for f in funds:
                code = f.get("code", "")
                all_codes.append(code)
                type_weight_map[code] = per_fund_w

        if not all_codes:
            return [], []

        # Fetch NAV data for each fund for the period
        fund_nav_history: dict[str, list[dict[str, Any]]] = {}
        for code in all_codes:
            pts = await self._get_nav_points_for_period(db, code, start_date, end_date)
            if pts:
                fund_nav_history[code] = pts

        if not fund_nav_history:
            return [], []

        # Generate monthly rebalance dates
        monthly_dates = self._get_monthly_dates(start_date, end_date)

        # Simulate
        portfolio_values: list[dict[str, object]] = []
        benchmark_values: list[dict[str, object]] = []

        # Starting capital
        capital = Decimal("10000")

        for i, rdate in enumerate(monthly_dates):
            if i == 0:
                # Initial allocation
                holdings: dict[str, tuple[Decimal, Decimal]] = {}
                # holdings: code -> (shares, weight)

                total_weight = Decimal("0")
                for code, w in type_weight_map.items():
                    if code not in fund_nav_history:
                        continue
                    nav_pt = self._find_closest(fund_nav_history[code], rdate)
                    if nav_pt is None:
                        continue
                    nav = nav_pt["nav"]
                    amt = capital * w
                    shares = amt / nav
                    holdings[code] = (shares, w)
                    total_weight += w

                # Rebalance total to 1.0
                if total_weight > 0:
                    for code in holdings:
                        s, w = holdings[code]
                        holdings[code] = (s, w / total_weight)

            else:
                # Rebalance monthly
                # Calculate current portfolio value
                total_value = Decimal("0")
                for code, (shares, _) in holdings.items():
                    if code not in fund_nav_history:
                        continue
                    nav_pt = self._find_closest(fund_nav_history[code], rdate)
                    if nav_pt is None:
                        continue
                    total_value += shares * nav_pt["nav"]

                if total_value <= 0:
                    total_value = capital

                # Apply friction proportional to portfolio turnover.
                # Only the portion of the portfolio that actually changes
                # hands incurs transaction costs, not the entire portfolio.
                # Estimate turnover as ~30% of portfolio per monthly rebalance.
                friction = total_value * FRICTION_RATE * Decimal("0.3")
                total_value -= friction

                # Reallocate
                new_holdings: dict[str, tuple[Decimal, Decimal]] = {}
                for code, w in type_weight_map.items():
                    if code not in fund_nav_history:
                        continue
                    nav_pt = self._find_closest(fund_nav_history[code], rdate)
                    if nav_pt is None:
                        continue
                    nav = nav_pt["nav"]
                    amt = total_value * w
                    shares = amt / nav
                    new_holdings[code] = (shares, w)

                holdings = new_holdings

            # Record portfolio NAV for this month
            total_nav = Decimal("0")
            for code, (shares, _) in holdings.items():
                if code not in fund_nav_history:
                    continue
                nav_pt = self._find_closest(fund_nav_history[code], rdate)
                if nav_pt is None:
                    continue
                total_nav += shares * nav_pt["nav"]

            portfolio_values.append({
                "date": rdate.isoformat(),
                "value": float(round(total_nav, 2)),
            })

            # Benchmark (HS300 proxy: equal-weighted average of all fund NAVs)
            bench_val = Decimal("0")
            bench_count = 0
            for code in all_codes:
                if code not in fund_nav_history:
                    continue
                nav_pt = self._find_closest(fund_nav_history[code], rdate)
                if nav_pt is None:
                    continue
                # Scale to start at 10000
                first_pt = self._find_closest(fund_nav_history[code], start_date)
                if first_pt and first_pt["nav"] != 0:
                    scaled = nav_pt["nav"] / first_pt["nav"] * Decimal("10000")
                else:
                    scaled = nav_pt["nav"]
                bench_val += scaled
                bench_count += 1

            if bench_count > 0:
                bench_val = bench_val / Decimal(str(bench_count))

            benchmark_values.append({
                "date": rdate.isoformat(),
                "value": float(round(bench_val, 2)),
            })

        return portfolio_values, benchmark_values

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def _calc_metrics(
        self, nav_series: list[dict[str, object]]
    ) -> dict[str, Any]:
        """Calculate performance metrics from NAV series."""
        if not nav_series or len(nav_series) < 2:
            return {
                "total_return": Decimal("0"),
                "annual_return": 0.0,
                "max_drawdown": Decimal("0"),
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
            }

        values = [Decimal(str(p["value"])) for p in nav_series]
        nav_decimals = values

        # Total return
        first = nav_decimals[0]
        last = nav_decimals[-1]
        total_return = (last - first) / first if first != 0 else Decimal("0")

        # Annual return
        months = len(nav_series)
        years = months / 12.0
        if years > 0 and first > 0:
            annual_return = float((last / first) ** Decimal(str(1 / years)) - 1)
        else:
            annual_return = 0.0

        # Max drawdown
        max_dd = calc_max_drawdown(nav_decimals)

        # Sharpe ratio from monthly returns
        monthly_rets: list[Decimal] = []
        for i in range(1, len(nav_decimals)):
            if nav_decimals[i - 1] != 0:
                mr = (nav_decimals[i] - nav_decimals[i - 1]) / nav_decimals[i - 1]
                monthly_rets.append(mr)

        sharpe = calc_sharpe_ratio(monthly_rets, risk_free_rate=0.03) if monthly_rets else 0.0

        # Win rate: fraction of positive months
        if monthly_rets:
            wins = sum(1 for r in monthly_rets if r > 0)
            win_rate = wins / len(monthly_rets)
        else:
            win_rate = 0.0

        return {
            "total_return": total_return,
            "annual_return": round(annual_return, 4),
            "max_drawdown": max_dd,
            "sharpe_ratio": round(sharpe, 4),
            "win_rate": round(win_rate, 4),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_monthly_dates(
        start: date, end: date
    ) -> list[date]:
        """Generate list of first-of-month dates in the range."""
        dates: list[date] = []
        current = date(start.year, start.month, 1)
        # Include start month
        while current <= end:
            if current >= start:
                dates.append(current)
            # Next month
            m = current.month + 1
            y = current.year
            if m > 12:
                m = 1
                y += 1
            current = date(y, m, 1)
        return dates

    @staticmethod
    def _find_closest(
        nav_points: list[dict[str, Any]], target_date: date
    ) -> dict[str, Any] | None:
        """Find the closest NAV point not after target_date."""
        best: dict[str, Any] | None = None
        for pt in nav_points:
            pt_date = pt.get("date")
            if isinstance(pt_date, str):
                pt_date = date.fromisoformat(pt_date)
            if pt_date <= target_date:
                best = pt
            else:
                break
        return best

    async def _get_nav_points(
        self, db: AsyncSession, fund_code: str, limit: int = 260
    ) -> list[dict[str, Any]]:
        """Fetch NAV points ascending."""
        q = (
            select(FundNav)
            .where(FundNav.fund_code == fund_code)
            .order_by(FundNav.date.asc())
            .limit(limit)
        )
        result = await db.execute(q)
        rows = result.scalars().all()
        return [
            {
                "date": r.date,
                "nav": r.nav,
                "accumulated_nav": r.accumulated_nav,
            }
            for r in rows
        ]

    async def _get_nav_points_for_period(
        self, db: AsyncSession, fund_code: str, start: date, end: date
    ) -> list[dict[str, Any]]:
        """Fetch NAV points within date range, ordered ascending."""
        q = (
            select(FundNav)
            .where(
                FundNav.fund_code == fund_code,
                FundNav.date >= start,
                FundNav.date <= end,
            )
            .order_by(FundNav.date.asc())
        )
        result = await db.execute(q)
        rows = result.scalars().all()
        return [
            {
                "date": r.date,
                "nav": r.nav,
                "accumulated_nav": r.accumulated_nav,
            }
            for r in rows
        ]

    @staticmethod
    def _empty_result(
        strategy: str, period: str, start_date: date, end_date: date
    ) -> dict[str, Any]:
        """Return an empty backtest result."""
        return {
            "strategy": strategy,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "total_return": Decimal("0"),
            "annual_return": 0.0,
            "max_drawdown": Decimal("0"),
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "nav_series": [],
            "benchmark_series": [],
        }
