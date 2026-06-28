"""
Fund service — business logic for fund market (行情) module.

All public methods return plain dicts consumed by API routes and
wrapped in the unified ``{code, message, data}`` envelope there.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any


from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundHolding, FundManager, FundNav
from app.schemas.fund import FundFilterParams, SortOrder
from app.services.cache_service import CacheService
from app.utils.finance import (
    calc_alpha_beta,
    calc_max_drawdown,
    calc_period_returns,
    calc_sharpe_ratio,
    calc_volatility,
)

logger = logging.getLogger(__name__)

# Map period strings to approximate trading-day counts
PERIOD_DAYS: dict[str, int] = {
    "1m": 22,
    "3m": 66,
    "6m": 130,
    "1y": 252,
    "all": 1260,  # roughly 5 years
}


class FundService:
    """Async service for fund queries, filtering, comparison, and analytics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.cache = CacheService()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> dict[str, Any]:
        """
        Fuzzy search by fund code or name.

        1. Try Redis ``fund:list:all`` cache first.
        2. Fallback to DB LIKE query.
        3. Attach latest NAV from Redis cache.
        4. Return paginated dict with ``items`` and ``total``.
        """
        # Try cache first for the full fund list
        cached = await self.cache.get_fund_list()
        if cached is not None and keyword:
            # Filter cached list by keyword
            kw = keyword.lower()
            matched = [
                f for f in cached
                if kw in (f.get("code", "") or "").lower()
                or kw in (f.get("name", "") or "").lower()
            ]
            total = len(matched)
            start = (page - 1) * page_size
            end = start + page_size
            page_items = matched[start:end]

            # Enrich with latest NAV from cache
            for item in page_items:
                code = item.get("code", "")
                nav_cache = await self.cache.get_latest_nav(code)
                if nav_cache:
                    item["latest_nav"] = nav_cache.get("nav")
                    item["daily_return"] = nav_cache.get("daily_return")

            return {"items": page_items, "total": total}

        # DB fallback
        query = select(Fund)
        if keyword:
            pattern = f"%{keyword}%"
            query = query.where(
                Fund.code.ilike(pattern) | Fund.name.ilike(pattern)
            )

        # Total count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Paginated rows
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        rows = result.scalars().all()

        items: list[dict[str, Any]] = []
        for row in rows:
            item = _fund_to_basic_dict(row)
            # Attach latest NAV
            nav_cache = await self.cache.get_latest_nav(row.code)
            if nav_cache:
                item["latest_nav"] = Decimal(nav_cache.get("nav", "0")) if nav_cache.get("nav") else None
                dr = nav_cache.get("daily_return")
                item["daily_return"] = Decimal(str(dr)) if dr else None
            else:
                item["latest_nav"] = None
                item["daily_return"] = None
            items.append(item)

        return {"items": items, "total": total}

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------
    async def filter_funds(self, filters: FundFilterParams) -> dict[str, Any]:
        """
        Multi-dimension fund filtering with dynamic sorting.

        Builds WHERE clauses dynamically based on provided filter fields
        and supports sort_by on any allowed field.
        """
        # Build base query joining with latest NAV subquery
        nav_sq = (
            select(
                FundNav.fund_code,
                FundNav.nav,
                FundNav.daily_return,
                func.row_number()
                .over(
                    partition_by=FundNav.fund_code,
                    order_by=FundNav.date.desc(),
                )
                .label("rn"),
            )
            .subquery()
        )

        latest_nav = (
            select(
                nav_sq.c.fund_code,
                nav_sq.c.nav.label("latest_nav"),
                nav_sq.c.daily_return,
            )
            .where(nav_sq.c.rn == 1)
            .subquery()
        )

        query = (
            select(
                Fund.code,
                Fund.name,
                Fund.type,
                Fund.scale,
                Fund.fee_rate,
                Fund.company,
                latest_nav.c.latest_nav,
                latest_nav.c.daily_return,
            )
            .select_from(Fund)
            .outerjoin(latest_nav, Fund.code == latest_nav.c.fund_code)
        )

        # Dynamic filters
        conditions: list[Any] = []

        if filters.type is not None:
            conditions.append(Fund.type == filters.type)
        if filters.min_scale is not None:
            conditions.append(Fund.scale >= filters.min_scale)
        if filters.max_scale is not None:
            conditions.append(Fund.scale <= filters.max_scale)
        if filters.max_fee is not None:
            conditions.append(Fund.fee_rate <= filters.max_fee)
        if filters.manager is not None:
            # Subquery on fund_managers
            manager_sq = (
                select(FundManager.fund_code)
                .where(FundManager.name.ilike(f"%{filters.manager}%"))
                .distinct()
                .subquery()
            )
            conditions.append(Fund.code.in_(select(manager_sq.c.fund_code)))
        if filters.company is not None:
            conditions.append(Fund.company.ilike(f"%{filters.company}%"))

        if conditions:
            query = query.where(and_(*conditions))

        # Count total
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Sorting
        sort_col = {
            "latest_nav": latest_nav.c.latest_nav,
            "daily_return": latest_nav.c.daily_return,
        }
        # For return-based sorts we need a derived value — use latest_nav as
        # a proxy and sort by nav column; actual year returns are computed
        # from period returns and sorted in-memory.
        sort_field = sort_col.get(
            filters.sort_by.value if filters.sort_by else "latest_nav",
            latest_nav.c.latest_nav,
        )
        if filters.order == SortOrder.ASC:
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())

        # Pagination
        query = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
        result = await self.db.execute(query)
        rows = result.all()

        items: list[dict[str, Any]] = []
        for row in rows:
            items.append({
                "code": row.code,
                "name": row.name,
                "type": row.type,
                "scale": row.scale,
                "fee_rate": row.fee_rate,
                "company": row.company,
                "latest_nav": row.latest_nav,
                "daily_return": row.daily_return,
                "ytd_return": None,    # computed in get_detail; placeholder here
                "one_year_return": None,
            })

        # If sort_by is a return field, sort in memory after computing returns
        if filters.sort_by and filters.sort_by.value not in ("latest_nav", "daily_return"):
            # For return-based sort, load NAV history for each fund and compute
            for item in items:
                nav_data = await self._get_nav_points(item["code"], limit=252)
                if nav_data:
                    period_returns = calc_period_returns(nav_data)
                    item["one_year_return"] = period_returns.get("one_year")
                    item["ytd_return"] = period_returns.get("ytd")
                    if filters.sort_by.value == "three_year_return":
                        nav_data_3y = await self._get_nav_points(item["code"], limit=756)
                        if nav_data_3y:
                            pr3 = calc_period_returns(nav_data_3y)
                            item["three_year_return"] = pr3.get("three_year")

            # Sort by the appropriate field
            reverse = filters.order == SortOrder.DESC
            if filters.sort_by.value == "one_year_return":
                items.sort(
                    key=lambda x: float(x.get("one_year_return") if x.get("one_year_return") is not None else -9999),
                    reverse=reverse,
                )
            elif filters.sort_by.value == "three_year_return":
                items.sort(
                    key=lambda x: float(x.get("three_year_return") if x.get("three_year_return") is not None else -9999),
                    reverse=reverse,
                )

        return {"items": items, "total": total}

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------
    async def get_detail(self, code: str) -> dict[str, Any]:
        """
        Aggregate full fund detail.

        1. Query funds table for basic info.
        2. Query fund_nav for latest NAV and period returns.
        3. Query fund_manager for manager info.
        4. Calculate risk metrics from historical NAV.
        """
        # 1. Basic info
        fund_q = select(Fund).where(Fund.code == code)
        fund_result = await self.db.execute(fund_q)
        fund = fund_result.scalar_one_or_none()
        if fund is None:
            return {}

        basic = _fund_to_basic_dict(fund)

        # 2. NAV data
        latest_nav_row_q = (
            select(FundNav)
            .where(FundNav.fund_code == code)
            .order_by(FundNav.date.desc())
            .limit(1)
        )
        latest_nav_result = await self.db.execute(latest_nav_row_q)
        latest_nav_row = latest_nav_result.scalar_one_or_none()

        nav_info: dict[str, Any] = {
            "latest_nav": None, "accumulated_nav": None,
            "daily_return": None, "weekly_return": None,
            "monthly_return": None, "three_month_return": None,
            "six_month_return": None, "ytd_return": None,
            "one_year_return": None, "three_year_return": None,
            "five_year_return": None,
        }

        if latest_nav_row:
            nav_info["latest_nav"] = latest_nav_row.nav
            nav_info["accumulated_nav"] = latest_nav_row.accumulated_nav
            nav_info["daily_return"] = latest_nav_row.daily_return

        # Period returns
        nav_history = await self._get_nav_points(code, limit=1260)  # 5 years
        if nav_history:
            period_returns = calc_period_returns(nav_history)
            for key in ("weekly_return", "monthly_return", "three_month_return",
                        "six_month_return", "ytd_return", "one_year_return",
                        "three_year_return", "five_year_return"):
                nav_info[key] = period_returns.get(
                    key.replace("_return", "")
                )
            nav_info["daily_return"] = (
                period_returns.get("daily") or nav_info["daily_return"]
            )

        basic["latest_nav"] = nav_info["latest_nav"]
        basic["daily_return"] = nav_info["daily_return"]
        basic["ytd_return"] = nav_info["ytd_return"]
        basic["one_year_return"] = nav_info["one_year_return"]

        # 3. Manager info
        manager_q = (
            select(FundManager)
            .where(FundManager.fund_code == code)
            .order_by(FundManager.start_date.desc())
            .limit(1)
        )
        manager_result = await self.db.execute(manager_q)
        manager_row = manager_result.scalar_one_or_none()

        manager_info: dict[str, Any] = {"name": None, "start_date": None, "tenure_return": None}
        if manager_row:
            manager_info = {
                "name": manager_row.name,
                "start_date": manager_row.start_date,
                "tenure_return": manager_row.tenure_return,
            }

        # 4. Risk metrics
        risk_metrics: dict[str, Any] = {
            "max_drawdown": None,
            "sharpe_ratio": None,
            "volatility": None,
            "alpha": None,
            "beta": None,
        }

        if nav_history and len(nav_history) >= 22:
            nav_values = [
                Decimal(str(pt["nav"])) if not isinstance(pt["nav"], Decimal) else pt["nav"]
                for pt in nav_history
            ]
            risk_metrics["max_drawdown"] = calc_max_drawdown(nav_values)

            # Daily returns for sharpe, volatility, alpha, beta
            daily_returns: list[Decimal] = []
            for i in range(1, len(nav_values)):
                if nav_values[i - 1] != 0:
                    daily_returns.append(
                        (nav_values[i] - nav_values[i - 1]) / nav_values[i - 1]
                    )

            if daily_returns:
                risk_metrics["sharpe_ratio"] = round(calc_sharpe_ratio(daily_returns), 4)
                risk_metrics["volatility"] = round(calc_volatility(daily_returns), 4)

                # Alpha/Beta requires benchmark — use self as proxy if no external
                # benchmark is available (beta ~= 1 by construction in that case)
                risk_metrics["alpha"], risk_metrics["beta"] = calc_alpha_beta(
                    daily_returns, daily_returns
                )

        return {
            "basic": basic,
            "nav": nav_info,
            "manager": manager_info,
            "risk_metrics": risk_metrics,
        }

    # ------------------------------------------------------------------
    # NAV history
    # ------------------------------------------------------------------
    async def get_nav_history(self, code: str, period: str = "1m") -> dict[str, Any]:
        """
        Get historical NAV data for a fund.

        *period*: 1m, 3m, 6m, 1y, all.

        Tries Redis cache first for short periods (30d), then DB.
        """
        limit = PERIOD_DAYS.get(period, 22)

        # Try Redis for short periods
        if period in ("1m",):
            cached = await self.cache.get_nav_30d(code)
            if cached:
                points = _normalize_nav_points(cached[:limit])
                return {"period": period, "points": points}

        # DB fallback
        points = await self._get_nav_points(code, limit=limit)
        return {"period": period, "points": _normalize_nav_points(points)}

    # ------------------------------------------------------------------
    # Compare
    # ------------------------------------------------------------------
    async def compare(self, codes: list[str]) -> dict[str, Any]:
        """
        Multi-fund comparison.

        Returns side-by-side key metrics and overlay NAV data for charts.
        """
        funds: list[dict[str, Any]] = []
        overlay: dict[str, list[dict[str, Any]]] = {}

        for code in codes:
            # Fetch fund info
            fund_q = select(Fund).where(Fund.code == code)
            fund_result = await self.db.execute(fund_q)
            fund = fund_result.scalar_one_or_none()
            if fund is None:
                continue

            # Latest NAV
            latest_nav_row_q = (
                select(FundNav)
                .where(FundNav.fund_code == code)
                .order_by(FundNav.date.desc())
                .limit(1)
            )
            latest_result = await self.db.execute(latest_nav_row_q)
            latest = latest_result.scalar_one_or_none()

            # NAV history for period returns and overlay
            nav_history = await self._get_nav_points(code, limit=252)
            period_returns: dict[str, Decimal | None] = {}
            if nav_history:
                period_returns = calc_period_returns(nav_history)

            # Risk metrics
            max_dd: Decimal | None = None
            volatility: float | None = None
            sharpe: float | None = None
            if nav_history and len(nav_history) >= 22:
                nav_vals = [
                    Decimal(str(pt["nav"])) if not isinstance(pt["nav"], Decimal) else pt["nav"]
                    for pt in nav_history
                ]
                max_dd = calc_max_drawdown(nav_vals)
                daily_rets: list[Decimal] = []
                for i in range(1, len(nav_vals)):
                    if nav_vals[i - 1] != 0:
                        daily_rets.append(
                            (nav_vals[i] - nav_vals[i - 1]) / nav_vals[i - 1]
                        )
                if daily_rets:
                    volatility = round(calc_volatility(daily_rets), 4)
                    sharpe = round(calc_sharpe_ratio(daily_rets), 4)

            funds.append({
                "code": fund.code,
                "name": fund.name,
                "latest_nav": latest.nav if latest else None,
                "daily_return": latest.daily_return if latest else None,
                "weekly_return": period_returns.get("weekly"),
                "monthly_return": period_returns.get("monthly"),
                "ytd_return": period_returns.get("ytd"),
                "one_year_return": period_returns.get("one_year"),
                "max_drawdown": max_dd,
                "volatility": volatility,
                "sharpe_ratio": sharpe,
            })

            # Overlay NAV points (last 30d for chart)
            overlay_pts = await self._get_nav_points(code, limit=30)
            overlay[code] = _normalize_nav_points(overlay_pts)

        return {"funds": funds, "overlay_points": overlay}

    # ------------------------------------------------------------------
    # Portfolio / holdings
    # ------------------------------------------------------------------
    async def get_portfolio(self, code: str) -> list[dict[str, Any]]:
        """
        Get a fund's top holdings (重仓股明细).

        Returns the most recent report's holdings from fund_holdings.
        """
        # Find the latest report_date for this fund
        latest_date_q = (
            select(func.max(FundHolding.report_date))
            .where(FundHolding.fund_code == code)
        )
        latest_date = (await self.db.execute(latest_date_q)).scalar()

        if latest_date is None:
            return []

        holdings_q = (
            select(FundHolding)
            .where(
                FundHolding.fund_code == code,
                FundHolding.report_date == latest_date,
            )
            .order_by(FundHolding.ratio.desc())
        )
        result = await self.db.execute(holdings_q)
        rows = result.scalars().all()

        return [
            {
                "stock_code": h.stock_code,
                "stock_name": h.stock_name,
                "ratio": h.ratio,
            }
            for h in rows
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_nav_points(
        self, code: str, limit: int = 252
    ) -> list[dict[str, Any]]:
        """Fetch raw NAV rows from DB, ordered by date descending, then reversed."""
        q = (
            select(FundNav)
            .where(FundNav.fund_code == code)
            .order_by(FundNav.date.desc())
            .limit(limit)
        )
        result = await self.db.execute(q)
        rows = list(result.scalars().all())
        # Reverse to ascending order
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


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _fund_to_basic_dict(fund: Fund) -> dict[str, Any]:
    """Convert a Fund ORM instance to a plain dict matching FundBasic."""
    return {
        "code": fund.code,
        "name": fund.name,
        "type": fund.type,
        "scale": fund.scale,
        "fee_rate": fund.fee_rate,
        "company": fund.company,
        "latest_nav": None,
        "daily_return": None,
        "ytd_return": None,
        "one_year_return": None,
    }


def _normalize_nav_points(
    points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure nav points have date as date and nav as Decimal."""
    result: list[dict[str, Any]] = []
    for pt in points:
        d = pt.get("date")
        if isinstance(d, str):
            d = date.fromisoformat(d)
        nav = pt.get("nav")
        if not isinstance(nav, Decimal):
            nav = Decimal(str(nav)) if nav is not None else Decimal("0")
        acc = pt.get("accumulated_nav")
        if not isinstance(acc, Decimal) and acc is not None:
            acc = Decimal(str(acc))
        result.append({
            "date": d,
            "nav": nav,
            "accumulated_nav": acc,
        })
    return result
