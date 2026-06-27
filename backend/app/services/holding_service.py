"""
Holding service — business logic for portfolio holding (持仓) management.

All public methods return plain dicts consumed by API routes and
wrapped in the unified ``{code, message, data}`` envelope there.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import FundTransaction, FundWatchlist, Holding
from app.schemas.holding import HoldingCreate, HoldingUpdate
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class HoldingService:
    """Async service for holding CRUD, watchlist, and P&L calculations."""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.cache = CacheService(redis)

    # ------------------------------------------------------------------
    # Holding CRUD
    # ------------------------------------------------------------------
    async def create(self, data: HoldingCreate) -> dict[str, Any]:
        """Create a new holding and record the initial buy transaction."""
        holding = Holding(
            fund_code=data.fund_code,
            fund_name=data.fund_name,
            buy_date=data.buy_date,
            amount=data.amount,
            shares=data.shares,
            buy_nav=data.buy_nav,
        )
        self.db.add(holding)
        await self.db.flush()

        # Record initial buy transaction
        txn = FundTransaction(
            holding_id=holding.id,
            type="buy",
            date=data.buy_date,
            amount=data.amount,
            shares=data.shares,
            price=data.buy_nav,
        )
        self.db.add(txn)
        await self.db.commit()

        # Re-query to get a fresh instance after commit
        result = await self.db.execute(select(Holding).where(Holding.id == holding.id))
        created = result.scalar_one()
        return _holding_to_dict(created)

    async def list_with_profit(self) -> dict[str, Any]:
        """
        List all holdings with real-time profit/loss calculations.

        1. Query all holdings from DB.
        2. For each, get latest_nav from Redis (or fallback to buy_nav).
        3. Calculate market_value, profit_loss, profit_loss_ratio.
        4. Calculate holding_ratio for each.
        5. Calculate today_profit estimate.
        6. Return items list and summary dict.
        """
        result = await self.db.execute(select(Holding).order_by(Holding.created_at.desc()))
        holdings: list[Holding] = list(result.scalars().all())

        if not holdings:
            return {
                "items": [],
                "summary": {
                    "total_asset": Decimal("0"),
                    "total_cost": Decimal("0"),
                    "total_profit": Decimal("0"),
                    "total_profit_ratio": None,
                    "today_profit": None,
                    "today_profit_ratio": None,
                    "holding_count": 0,
                    "best_fund": None,
                    "worst_fund": None,
                },
            }

        # Step 1: Enrich each holding with latest NAV and compute individual metrics
        enriched: list[dict[str, Any]] = []
        for h in holdings:
            item = _holding_to_dict(h)

            # Get latest NAV from Redis
            nav_cache = await self.cache.get_latest_nav(h.fund_code)
            latest_nav: Decimal | None = None
            daily_return: Decimal | None = None

            if nav_cache:
                nav_str = nav_cache.get("nav")
                dr_str = nav_cache.get("daily_return")
                if nav_str:
                    latest_nav = Decimal(str(nav_str))
                if dr_str:
                    daily_return = Decimal(str(dr_str))

            # Fallback to buy_nav if no cached NAV
            if latest_nav is None:
                latest_nav = h.buy_nav

            item["latest_nav"] = latest_nav
            item["daily_return"] = daily_return

            # market_value = shares * latest_nav
            if latest_nav is not None and h.shares is not None:
                item["market_value"] = h.shares * latest_nav
            else:
                item["market_value"] = h.amount  # fallback to cost

            # profit_loss = market_value - amount
            item["profit_loss"] = item["market_value"] - h.amount

            # profit_loss_ratio
            if h.amount and h.amount != 0:
                item["profit_loss_ratio"] = item["profit_loss"] / h.amount
            else:
                item["profit_loss_ratio"] = None

            # holding_ratio (will be set after total calculation)
            enriched.append(item)

        # Step 2: Calculate totals
        total_market_value = sum(
            (item["market_value"] for item in enriched),
            Decimal("0"),
        )
        total_cost = sum((h.amount for h in holdings), Decimal("0"))

        # Step 3: Set holding_ratio for each
        for item in enriched:
            if total_market_value and total_market_value != 0:
                item["holding_ratio"] = item["market_value"] / total_market_value
            else:
                item["holding_ratio"] = Decimal("0")

        # Step 4: Calculate total_profit and ratio
        total_profit = total_market_value - total_cost
        total_profit_ratio: Decimal | None = None
        if total_cost and total_cost != 0:
            total_profit_ratio = total_profit / total_cost

        # Step 5: Calculate today_profit (sum of shares * today_return)
        today_profit: Decimal | None = None
        today_profit_ratio: Decimal | None = None
        today_contributions: list[Decimal] = []
        for h in holdings:
            nav_cache = await self.cache.get_latest_nav(h.fund_code)
            if nav_cache:
                nav_str = nav_cache.get("nav")
                dr_str = nav_cache.get("daily_return")
                if nav_str and dr_str:
                    latest_nav = Decimal(str(nav_str))
                    daily_return = Decimal(str(dr_str))
                    # today_profit contribution = shares * latest_nav * daily_return
                    contrib = h.shares * latest_nav * daily_return
                    today_contributions.append(contrib)

        if today_contributions:
            today_profit = sum(today_contributions, Decimal("0"))

        # today_profit_ratio
        if total_cost and total_cost != 0 and today_profit is not None:
            today_profit_ratio = today_profit / total_cost

        # Step 6: Find best and worst performing funds
        funded = [item for item in enriched if item["profit_loss_ratio"] is not None]
        best_fund: dict[str, Any] | None = None
        worst_fund: dict[str, Any] | None = None
        if funded:
            best_item = max(funded, key=lambda x: x["profit_loss_ratio"])
            worst_item = min(funded, key=lambda x: x["profit_loss_ratio"])
            best_fund = {
                "fund_code": best_item["fund_code"],
                "fund_name": best_item["fund_name"],
                "profit_loss_ratio": best_item["profit_loss_ratio"],
            }
            worst_fund = {
                "fund_code": worst_item["fund_code"],
                "fund_name": worst_item["fund_name"],
                "profit_loss_ratio": worst_item["profit_loss_ratio"],
            }

        return {
            "items": enriched,
            "summary": {
                "total_asset": total_market_value,
                "total_cost": total_cost,
                "total_profit": total_profit,
                "total_profit_ratio": total_profit_ratio,
                "today_profit": today_profit,
                "today_profit_ratio": today_profit_ratio,
                "holding_count": len(holdings),
                "best_fund": best_fund,
                "worst_fund": worst_fund,
            },
        }

    async def get(self, id: int) -> dict[str, Any] | None:
        """Get a single holding with real-time P&L details."""
        result = await self.db.execute(select(Holding).where(Holding.id == id))
        holding = result.scalar_one_or_none()
        if holding is None:
            return None

        item = _holding_to_dict(holding)

        # Get latest NAV from Redis
        nav_cache = await self.cache.get_latest_nav(holding.fund_code)
        latest_nav: Decimal | None = None
        daily_return: Decimal | None = None
        if nav_cache:
            nav_str = nav_cache.get("nav")
            dr_str = nav_cache.get("daily_return")
            if nav_str:
                latest_nav = Decimal(str(nav_str))
            if dr_str:
                daily_return = Decimal(str(dr_str))

        if latest_nav is None:
            latest_nav = holding.buy_nav

        item["latest_nav"] = latest_nav
        item["daily_return"] = daily_return

        if latest_nav is not None and holding.shares is not None:
            item["market_value"] = holding.shares * latest_nav
        else:
            item["market_value"] = holding.amount

        item["profit_loss"] = item["market_value"] - holding.amount

        if holding.amount and holding.amount != 0:
            item["profit_loss_ratio"] = item["profit_loss"] / holding.amount
        else:
            item["profit_loss_ratio"] = None

        # For single holding, ratio is 1.0 (100%)
        item["holding_ratio"] = Decimal("1.0")

        return item

    async def update(self, id: int, data: HoldingUpdate) -> dict[str, Any] | None:
        """Update a holding.  *fund_code* cannot be changed."""
        result = await self.db.execute(select(Holding).where(Holding.id == id))
        holding = result.scalar_one_or_none()
        if holding is None:
            return None

        if data.amount is not None:
            holding.amount = data.amount
        if data.shares is not None:
            holding.shares = data.shares
        if data.buy_date is not None:
            holding.buy_date = data.buy_date
        if data.buy_nav is not None:
            holding.buy_nav = data.buy_nav

        self.db.add(holding)
        await self.db.commit()

        # Re-query to get a fresh instance after commit
        result = await self.db.execute(select(Holding).where(Holding.id == id))
        refreshed = result.scalar_one()
        return _holding_to_dict(refreshed)

    async def delete(self, id: int) -> bool:
        """Delete a holding — cascading deletes apply to related transactions."""
        result = await self.db.execute(select(Holding).where(Holding.id == id))
        holding = result.scalar_one_or_none()
        if holding is None:
            return False

        await self.db.delete(holding)
        await self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------
    async def add_to_watchlist(self, fund_code: str, fund_name: str) -> dict[str, Any]:
        """Add a fund to the watchlist (upsert-style: skip if already exists)."""
        result = await self.db.execute(
            select(FundWatchlist).where(FundWatchlist.fund_code == fund_code)
        )
        existing = result.scalar_one_or_none()

        if existing:
            return _watchlist_to_dict(existing)

        wl = FundWatchlist(fund_code=fund_code, fund_name=fund_name)
        self.db.add(wl)
        await self.db.commit()

        # Re-query to get a fresh instance after commit
        result = await self.db.execute(
            select(FundWatchlist).where(FundWatchlist.fund_code == fund_code)
        )
        created = result.scalar_one()
        return _watchlist_to_dict(created)

    async def list_watchlist(self) -> list[dict[str, Any]]:
        """List all watchlist entries enriched with latest NAV data."""
        result = await self.db.execute(
            select(FundWatchlist).order_by(FundWatchlist.added_at.desc())
        )
        rows = result.scalars().all()
        items: list[dict[str, Any]] = []
        for r in rows:
            item = _watchlist_to_dict(r)
            # Enrich with latest NAV from Redis
            nav_cache = await self.cache.get_latest_nav(r.fund_code)
            if nav_cache:
                nav_str = nav_cache.get("nav")
                dr_str = nav_cache.get("daily_return")
                item["latest_nav"] = Decimal(str(nav_str)) if nav_str else None
                item["daily_return"] = Decimal(str(dr_str)) if dr_str else None
            else:
                item["latest_nav"] = None
                item["daily_return"] = None
            items.append(item)
        return items

    async def remove_from_watchlist(self, fund_code: str) -> bool:
        """Remove a fund from the watchlist by its fund_code."""
        result = await self.db.execute(
            select(FundWatchlist).where(FundWatchlist.fund_code == fund_code)
        )
        wl = result.scalar_one_or_none()
        if wl is None:
            return False

        await self.db.delete(wl)
        await self.db.commit()
        return True


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _holding_to_dict(h: Holding) -> dict[str, Any]:
    """Convert a Holding ORM instance to a plain dict."""
    return {
        "id": h.id,
        "fund_code": h.fund_code,
        "fund_name": h.fund_name,
        "buy_date": h.buy_date,
        "amount": h.amount,
        "shares": h.shares,
        "buy_nav": h.buy_nav,
        "latest_nav": None,
        "market_value": None,
        "profit_loss": None,
        "profit_loss_ratio": None,
        "holding_ratio": None,
        "created_at": h.created_at,
        "updated_at": h.updated_at,
    }


def _watchlist_to_dict(w: FundWatchlist) -> dict[str, Any]:
    """Convert a FundWatchlist ORM instance to a plain dict."""
    return {
        "fund_code": w.fund_code,
        "fund_name": w.fund_name,
        "latest_nav": None,
        "daily_return": None,
        "added_at": w.added_at,
    }
