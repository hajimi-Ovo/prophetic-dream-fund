"""
Dashboard service — portfolio-level aggregation and analytics.

Provides dashboard summary, returns chart, asset allocation, and risk metrics.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import FundNav
from app.models.holding import Holding
from app.services.cache_service import CacheService
from app.utils.finance import (
    calc_max_drawdown,
    calc_sharpe_ratio,
    calc_volatility,
)

logger = logging.getLogger(__name__)

# Period to approximate trading-day count
PERIOD_DAYS: dict[str, int] = {
    "1m": 22,
    "3m": 66,
    "6m": 130,
    "1y": 252,
    "all": 1260,
}


class DashboardService:
    """Async service for dashboard aggregation and portfolio analytics."""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.cache = CacheService(redis)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    async def get_summary(self) -> dict[str, Any]:
        """
        Aggregate total asset, profit, today_profit from all holdings.

        Finds best/worst performing fund by profit_loss_ratio.
        """
        result = await self.db.execute(select(Holding))
        holdings: list[Holding] = list(result.scalars().all())

        if not holdings:
            return {
                "total_asset": Decimal("0"),
                "total_cost": Decimal("0"),
                "total_profit": Decimal("0"),
                "total_profit_ratio": None,
                "today_profit": Decimal("0"),
                "today_profit_ratio": None,
                "holding_count": 0,
            }

        total_cost = Decimal("0")
        total_market_value = Decimal("0")
        today_profit = Decimal("0")
        perf_list: list[dict[str, Any]] = []

        for h in holdings:
            total_cost += h.amount

            # Get latest NAV and daily_return from Redis
            nav_cache = await self.cache.get_latest_nav(h.fund_code)
            latest_nav: Decimal | None = h.buy_nav
            daily_return: Decimal | None = None

            if nav_cache:
                nav_str = nav_cache.get("nav")
                dr_str = nav_cache.get("daily_return")
                if nav_str:
                    latest_nav = Decimal(str(nav_str))
                if dr_str:
                    daily_return = Decimal(str(dr_str))

            # Market value
            if latest_nav is not None:
                mv = h.shares * latest_nav
            else:
                mv = h.amount

            total_market_value += mv

            # Today profit contribution
            if latest_nav is not None and daily_return is not None:
                today_profit += h.shares * latest_nav * daily_return

            # For best/worst fund determination
            profit_loss = mv - h.amount
            profit_loss_ratio: Decimal | None = None
            if h.amount and h.amount != 0:
                profit_loss_ratio = profit_loss / h.amount

            perf_list.append({
                "fund_code": h.fund_code,
                "fund_name": h.fund_name,
                "profit_loss_ratio": profit_loss_ratio,
            })

        total_profit = total_market_value - total_cost
        total_profit_ratio: Decimal | None = None
        if total_cost and total_cost != 0:
            total_profit_ratio = total_profit / total_cost

        today_profit_ratio: Decimal | None = None
        if total_cost and total_cost != 0:
            today_profit_ratio = today_profit / total_cost

        return {
            "total_asset": total_market_value,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "total_profit_ratio": total_profit_ratio,
            "today_profit": today_profit,
            "today_profit_ratio": today_profit_ratio,
            "holding_count": len(holdings),
        }

    # ------------------------------------------------------------------
    # Returns Chart
    # ------------------------------------------------------------------
    async def get_returns_chart(self, period: str) -> dict[str, Any]:
        """
        Generate cumulative returns curve (share-weighted composite).

        Includes benchmark (HS300) comparison data if available.

        Period mapping: 1m=22d, 3m=66d, 6m=130d, 1y=252d, all=max.
        """
        limit = PERIOD_DAYS.get(period, 22)

        result = await self.db.execute(select(Holding))
        holdings: list[Holding] = list(result.scalars().all())

        if not holdings:
            return {"period": period, "points": [], "benchmark_points": []}

        # Build share-weighted composite NAV series
        # Step 1: Fetch NAV history for each holding's fund_code
        # Step 2: For each date, compute weighted composite NAV
        fund_nav_series: dict[str, list[dict[str, Any]]] = {}
        for h in holdings:
            nav_data = await self._get_nav_points(h.fund_code, limit=limit)
            if nav_data:
                fund_nav_series[h.fund_code] = nav_data

        if not fund_nav_series:
            return {"period": period, "points": [], "benchmark_points": []}

        # Step 2: Build date-indexed weighted composite
        # Collect all unique dates across all fund NAV series
        all_dates: set[date] = set()
        for nav_list in fund_nav_series.values():
            for pt in nav_list:
                d = pt.get("date")
                if isinstance(d, str):
                    d = date.fromisoformat(d)
                all_dates.add(d)

        sorted_dates = sorted(all_dates)

        # For each date, compute weighted NAV
        # Build a lookup: fund_code -> {date -> nav}
        nav_lookup: dict[str, dict[date, Decimal]] = defaultdict(dict)
        for code, nav_list in fund_nav_series.items():
            for pt in nav_list:
                d = pt.get("date")
                if isinstance(d, str):
                    d = date.fromisoformat(d)
                nav = pt.get("nav")
                if not isinstance(nav, Decimal):
                    nav = Decimal(str(nav)) if nav is not None else Decimal("1")
                nav_lookup[code][d] = nav

        # Build holdings lookup: fund_code -> (shares, amount)
        holding_info: dict[str, tuple[Decimal, Decimal]] = {}
        for h in holdings:
            holding_info[h.fund_code] = (h.shares, h.amount)

        # Compute composite points
        points: list[dict[str, Any]] = []
        for d in sorted_dates:
            total_mv = Decimal("0")
            total_shares = Decimal("0")
            for code, (shares, amount) in holding_info.items():
                nav_at_date = nav_lookup.get(code, {}).get(d)
                if nav_at_date is not None:
                    total_mv += shares * nav_at_date
                    total_shares += shares

            if total_shares > 0:
                composite_nav = total_mv / total_shares
            else:
                composite_nav = Decimal("1")

            points.append({
                "date": d,
                "portfolio_nav": composite_nav,
                "benchmark_nav": None,
            })

        # Fetch benchmark (HS300) NAV for comparison
        benchmark_nav_map: dict[date, Decimal] = {}
        try:
            benchmark_nav_data = await self._get_nav_points("000300", limit=limit)
            if benchmark_nav_data:
                for pt in benchmark_nav_data:
                    d = pt.get("date")
                    if isinstance(d, str):
                        d = date.fromisoformat(d)
                    nav = pt.get("nav")
                    if not isinstance(nav, Decimal):
                        nav = Decimal(str(nav)) if nav is not None else Decimal("1")
                    benchmark_nav_map[d] = nav
        except Exception:
            logger.debug("No benchmark (HS300) data available", exc_info=True)

        # Merge benchmark data into points
        if benchmark_nav_map:
            for pt in points:
                bnav = benchmark_nav_map.get(pt["date"])
                if bnav is not None:
                    pt["benchmark_nav"] = bnav

        # Transform to frontend-compatible format: {date, returns, benchmark_returns}
        result_points: list[dict[str, Any]] = []
        if points:
            base_nav = points[0]["portfolio_nav"]
            base_benchmark = points[0].get("benchmark_nav")

            for pt in points:
                d = pt["date"]
                nav = pt["portfolio_nav"]
                bench_nav = pt.get("benchmark_nav")
                cumulative_return = (nav - base_nav) / base_nav if base_nav != 0 else Decimal("0")
                entry: dict[str, Any] = {
                    "date": d.isoformat() if isinstance(d, date) else str(d),
                    "returns": float(round(cumulative_return, 6)),
                }
                if bench_nav is not None and base_benchmark is not None and base_benchmark != 0:
                    benchmark_return = (bench_nav - base_benchmark) / base_benchmark
                    entry["benchmark_returns"] = float(round(benchmark_return, 6))
                result_points.append(entry)

        return result_points

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------
    async def get_allocation(self) -> dict[str, Any]:
        """
        Group holdings by fund type to produce pie chart data.

        Returns [{type, ratio, amount, fund_count}].

        Fund type is determined from the fund record in the funds table;
        falls back to "unknown" if the fund cannot be found.
        """
        from app.models.fund import Fund

        result = await self.db.execute(select(Holding))
        holdings: list[Holding] = list(result.scalars().all())

        if not holdings:
            return {"items": []}

        # Build fund_code -> type mapping from funds table
        codes = list({h.fund_code for h in holdings})
        fund_type_map: dict[str, str] = {}
        if codes:
            fund_result = await self.db.execute(
                select(Fund.code, Fund.type).where(Fund.code.in_(codes))
            )
            for row in fund_result.all():
                fund_type_map[row.code] = row.type or "unknown"

        # Calculate market value per holding
        type_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"type": "", "amount": Decimal("0"), "fund_count": 0}
        )

        total_mv = Decimal("0")
        for h in holdings:
            nav_cache = await self.cache.get_latest_nav(h.fund_code)
            latest_nav = h.buy_nav
            if nav_cache:
                nav_str = nav_cache.get("nav")
                if nav_str:
                    latest_nav = Decimal(str(nav_str))
            mv = h.shares * latest_nav if latest_nav else h.amount
            total_mv += mv

            fund_type = fund_type_map.get(h.fund_code, "unknown")
            if not type_data[fund_type]["type"]:
                type_data[fund_type]["type"] = fund_type
            type_data[fund_type]["amount"] += mv
            type_data[fund_type]["fund_count"] += 1

        items: list[dict[str, Any]] = []
        for ft, data in type_data.items():
            ratio = (data["amount"] / total_mv) if total_mv != 0 else Decimal("0")
            items.append({
                "fund_type": data["type"],
                "ratio": ratio,
                "market_value": data["amount"],
                "count": data["fund_count"],
            })

        # Sort by amount descending
        items.sort(key=lambda x: x["market_value"], reverse=True)

        return items

    # ------------------------------------------------------------------
    # Risk Metrics
    # ------------------------------------------------------------------
    async def get_risk_metrics(self) -> dict[str, Any]:
        """
        Calculate portfolio-level risk metrics using weighted returns.

        Computes:
        - max_drawdown: from the composite portfolio NAV series
        - sharpe_ratio: annualized Sharpe of the portfolio
        - volatility: annualized volatility of the portfolio
        """
        result = await self.db.execute(select(Holding))
        holdings: list[Holding] = list(result.scalars().all())

        if not holdings:
            return {
                "max_drawdown": None,
                "sharpe_ratio": None,
                "volatility": None,
            }

        # Fetch 1-year NAV history for each holding
        fund_nav_series: dict[str, list[dict[str, Any]]] = {}
        for h in holdings:
            nav_data = await self._get_nav_points(h.fund_code, limit=252)
            if nav_data:
                fund_nav_series[h.fund_code] = nav_data

        if not fund_nav_series:
            return {
                "max_drawdown": None,
                "sharpe_ratio": None,
                "volatility": None,
            }

        # Build date-indexed composite NAV series
        all_dates: set[date] = set()
        for nav_list in fund_nav_series.values():
            for pt in nav_list:
                d = pt.get("date")
                if isinstance(d, str):
                    d = date.fromisoformat(d)
                all_dates.add(d)

        sorted_dates = sorted(all_dates)

        nav_lookup: dict[str, dict[date, Decimal]] = defaultdict(dict)
        for code, nav_list in fund_nav_series.items():
            for pt in nav_list:
                d = pt.get("date")
                if isinstance(d, str):
                    d = date.fromisoformat(d)
                nav = pt.get("nav")
                if not isinstance(nav, Decimal):
                    nav = Decimal(str(nav)) if nav is not None else Decimal("1")
                nav_lookup[code][d] = nav

        holding_info: dict[str, tuple[Decimal, Decimal]] = {}
        for h in holdings:
            holding_info[h.fund_code] = (h.shares, h.amount)

        composite_nav_series: list[Decimal] = []
        for d in sorted_dates:
            total_mv = Decimal("0")
            total_shares = Decimal("0")
            for code, (shares, _amount) in holding_info.items():
                nav_at_date = nav_lookup.get(code, {}).get(d)
                if nav_at_date is not None:
                    total_mv += shares * nav_at_date
                    total_shares += shares

            if total_shares > 0:
                composite_nav_series.append(total_mv / total_shares)

        # Calculate risk metrics
        max_drawdown = calc_max_drawdown(composite_nav_series) if len(composite_nav_series) >= 2 else None

        # Daily returns from composite NAV
        daily_returns: list[Decimal] = []
        for i in range(1, len(composite_nav_series)):
            if composite_nav_series[i - 1] != 0:
                daily_returns.append(
                    (composite_nav_series[i] - composite_nav_series[i - 1])
                    / composite_nav_series[i - 1]
                )

        sharpe_ratio: float | None = None
        volatility: float | None = None
        if len(daily_returns) >= 2:
            sharpe_ratio = round(calc_sharpe_ratio(daily_returns), 4)
            volatility = round(calc_volatility(daily_returns), 4)

        return {
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "volatility": volatility,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_nav_points(
        self, code: str, limit: int = 252
    ) -> list[dict[str, Any]]:
        """Fetch NAV points from DB for a given fund code, ascending by date."""
        q = (
            select(FundNav)
            .where(FundNav.fund_code == code)
            .order_by(FundNav.date.desc())
            .limit(limit)
        )
        result = await self.db.execute(q)
        rows = list(result.scalars().all())
        # Reverse to ascending order for time-series calculations
        rows = list(reversed(rows))
        return [
            {
                "date": r.date,
                "nav": r.nav,
                "accumulated_nav": r.accumulated_nav,
                "daily_return": r.daily_return,
            }
            for r in rows
        ]
