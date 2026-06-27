"""
Unit tests for HoldingService — mock DB and Redis.

Verifies create, list_with_profit, update, delete, and watchlist flows.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.holding import HoldingCreate, HoldingUpdate
from app.services.holding_service import HoldingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_db() -> MagicMock:
    """Return a fully mocked AsyncSession."""
    db = MagicMock(spec=AsyncSession)
    return db


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Return a fully mocked Redis client."""
    redis = AsyncMock()
    redis.hgetall.return_value = {}
    redis.get.return_value = None
    return redis


@pytest.fixture
def service(mock_db: MagicMock, mock_redis: AsyncMock) -> HoldingService:
    """Return a HoldingService with mocked dependencies."""
    return HoldingService(mock_db, mock_redis)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_holding_row(
    id: int = 1,
    fund_code: str = "000001",
    fund_name: str = "Test Fund",
    amount: Decimal = Decimal("10000.00"),
    shares: Decimal = Decimal("5000.0000"),
    buy_nav: Decimal | None = Decimal("2.0000"),
) -> MagicMock:
    """Create a mock Holding ORM row."""
    h = MagicMock()
    h.id = id
    h.fund_code = fund_code
    h.fund_name = fund_name
    h.buy_date = date(2025, 1, 15)
    h.amount = amount
    h.shares = shares
    h.buy_nav = buy_nav
    h.created_at = datetime(2025, 1, 15, 10, 0, 0)
    h.updated_at = datetime(2025, 1, 15, 10, 0, 0)
    h.user_id = None
    return h


def _setup_execute_return_scalars(mock_db: MagicMock, rows: list[Any]) -> None:
    """Set up mock DB execute() -> scalars() -> all() chain."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result


def _setup_execute_return_scalar_one_or_none(mock_db: MagicMock, row: Any) -> None:
    """Set up mock DB execute() -> scalar_one_or_none() chain."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    mock_db.execute.return_value = mock_result


# ---------------------------------------------------------------------------
# Tests: create
# ---------------------------------------------------------------------------
class TestCreate:
    """HoldingService.create tests."""

    async def test_create_holding_success(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Create a holding with transaction record."""
        data = HoldingCreate(
            fund_code="000001",
            fund_name="Test Fund",
            buy_date=date(2025, 6, 1),
            amount=Decimal("10000.00"),
            shares=Decimal("5000.0000"),
            buy_nav=Decimal("2.0000"),
        )

        # Mock the flush to set id on the holding
        created_holding = _make_holding_row(id=1)

        async def _fake_flush() -> None:
            pass

        mock_db.flush = AsyncMock(side_effect=_fake_flush)
        mock_db.commit = AsyncMock()

        # After commit, the service re-queries: set up scalar_one() for re-query
        re_query_result = MagicMock()
        re_query_result.scalar_one.return_value = created_holding
        mock_db.execute.return_value = re_query_result

        result = await service.create(data)

        assert result["fund_code"] == "000001"
        assert result["fund_name"] == "Test Fund"
        assert result["amount"] == Decimal("10000.00")
        assert result["shares"] == Decimal("5000.0000")
        # Verify that a FundTransaction was added
        assert mock_db.add.call_count == 2  # holding + txn
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: list_with_profit
# ---------------------------------------------------------------------------
class TestListWithProfit:
    """HoldingService.list_with_profit tests."""

    async def test_empty_holdings(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """No holdings returns empty list and zero summary."""
        _setup_execute_return_scalars(mock_db, [])

        result = await service.list_with_profit()

        assert result["items"] == []
        assert result["summary"]["holding_count"] == 0
        assert result["summary"]["total_asset"] == Decimal("0")

    async def test_list_with_nav_from_cache(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Holdings enriched with latest NAV from Redis cache."""
        h = _make_holding_row(id=1, amount=Decimal("10000.00"), shares=Decimal("5000.0000"))
        _setup_execute_return_scalars(mock_db, [h])

        # Mock Redis to return NAV data
        mock_redis.hgetall.return_value = {
            "nav": "2.5000",
            "daily_return": "0.0100",
        }

        result = await service.list_with_profit()

        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["latest_nav"] == Decimal("2.5000")
        # market_value = 5000 * 2.5 = 12500
        assert item["market_value"] == Decimal("12500.00")
        # profit_loss = 12500 - 10000 = 2500
        assert item["profit_loss"] == Decimal("2500.00")
        # profit_loss_ratio = 2500 / 10000 = 0.25
        assert item["profit_loss_ratio"] == Decimal("0.25")
        # holding_ratio = 1.0 (single holding)
        assert item["holding_ratio"] == Decimal("1.0")

        summary = result["summary"]
        assert summary["total_asset"] == Decimal("12500.00")
        assert summary["total_cost"] == Decimal("10000.00")
        assert summary["total_profit"] == Decimal("2500.00")
        assert summary["holding_count"] == 1

    async def test_list_multiple_holdings_with_ratios(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Multiple holdings get correct holding_ratios."""
        h1 = _make_holding_row(id=1, fund_code="000001", amount=Decimal("10000.00"), shares=Decimal("5000.0000"))
        h2 = _make_holding_row(id=2, fund_code="000002", fund_name="Fund B", amount=Decimal("5000.00"), shares=Decimal("2500.0000"))
        _setup_execute_return_scalars(mock_db, [h1, h2])

        # Different NAVs for different funds
        mock_redis.hgetall.side_effect = [
            {"nav": "2.5000", "daily_return": "0.0100"},   # fund 000001
            {"nav": "3.0000", "daily_return": "0.0050"},   # fund 000002
        ]

        result = await service.list_with_profit()

        items = result["items"]
        # h1: mv = 5000 * 2.5 = 12500
        # h2: mv = 2500 * 3.0 = 7500
        # total mv = 20000
        assert items[0]["market_value"] == Decimal("12500.00")
        assert items[1]["market_value"] == Decimal("7500.00")
        assert items[0]["holding_ratio"] == Decimal("0.625")  # 12500/20000
        assert items[1]["holding_ratio"] == Decimal("0.375")  # 7500/20000

        assert result["summary"]["total_asset"] == Decimal("20000.00")

        # Best and worst fund
        assert result["summary"]["best_fund"]["fund_code"] == "000002"  # 50% return vs 25%
        assert result["summary"]["worst_fund"]["fund_code"] == "000001"

    async def test_today_profit_calculation(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Today's profit is calculated from daily returns and latest NAV."""
        h = _make_holding_row(id=1, amount=Decimal("10000.00"), shares=Decimal("5000.0000"))
        _setup_execute_return_scalars(mock_db, [h])

        mock_redis.hgetall.return_value = {
            "nav": "2.0000",
            "daily_return": "0.0200",  # 2% daily gain
        }

        result = await service.list_with_profit()

        # today_profit contribution = 5000 * 2.0 * 0.02 = 200
        assert result["summary"]["today_profit"] == Decimal("200.00")


# ---------------------------------------------------------------------------
# Tests: update
# ---------------------------------------------------------------------------
class TestUpdate:
    """HoldingService.update tests."""

    async def test_update_holding_success(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Update holding fields (fund_code is not in HoldingUpdate)."""
        h = _make_holding_row(id=1)

        # First execute: scalar_one_or_none returns h (find holding)
        # Second execute: scalar_one returns h (re-query after commit)
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = h
        second_result = MagicMock()
        second_result.scalar_one.return_value = h
        mock_db.execute.side_effect = [first_result, second_result]

        mock_db.commit = AsyncMock()

        data = HoldingUpdate(
            amount=Decimal("15000.00"),
            shares=Decimal("7500.0000"),
        )

        result = await service.update(1, data)

        assert result is not None
        assert result["fund_code"] == "000001"  # unchanged
        # The mock object's attributes are set by the service
        assert h.amount == Decimal("15000.00")
        assert h.shares == Decimal("7500.0000")

    async def test_update_nonexistent(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Update non-existent holding returns None."""
        _setup_execute_return_scalar_one_or_none(mock_db, None)

        data = HoldingUpdate(amount=Decimal("15000.00"))
        result = await service.update(999, data)

        assert result is None

    async def test_update_partial_fields(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Only provided fields are updated."""
        h = _make_holding_row(id=1, amount=Decimal("10000.00"), shares=Decimal("5000.0000"))

        # Two execute calls: find holding + re-query after commit
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = h
        second_result = MagicMock()
        second_result.scalar_one.return_value = h
        mock_db.execute.side_effect = [first_result, second_result]

        mock_db.commit = AsyncMock()

        # Only update amount, not shares
        data = HoldingUpdate(amount=Decimal("20000.00"))

        result = await service.update(1, data)

        assert result is not None
        assert h.amount == Decimal("20000.00")
        assert h.shares == Decimal("5000.0000")  # unchanged


# ---------------------------------------------------------------------------
# Tests: delete
# ---------------------------------------------------------------------------
class TestDelete:
    """HoldingService.delete tests."""

    async def test_delete_success(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Delete an existing holding returns True."""
        h = _make_holding_row(id=1)
        _setup_execute_return_scalar_one_or_none(mock_db, h)

        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        result = await service.delete(1)

        assert result is True
        mock_db.delete.assert_awaited_once_with(h)
        mock_db.commit.assert_awaited_once()

    async def test_delete_nonexistent(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Delete non-existent holding returns False."""
        _setup_execute_return_scalar_one_or_none(mock_db, None)

        result = await service.delete(999)

        assert result is False


# ---------------------------------------------------------------------------
# Tests: watchlist
# ---------------------------------------------------------------------------
class TestWatchlist:
    """HoldingService watchlist tests."""

    async def test_add_to_watchlist_new(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Add new fund to watchlist."""
        # First execute: scalar_one_or_none returns None (doesn't exist)
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = None

        # After commit, re-query: scalar_one returns new entry
        wl = MagicMock()
        wl.fund_code = "000001"
        wl.fund_name = "Test Fund"
        wl.added_at = datetime(2025, 6, 1)
        second_result = MagicMock()
        second_result.scalar_one.return_value = wl

        mock_db.execute.side_effect = [first_result, second_result]

        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        result = await service.add_to_watchlist("000001", "Test Fund")

        assert result["fund_code"] == "000001"
        assert result["fund_name"] == "Test Fund"

    async def test_add_to_watchlist_duplicate(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Adding existing fund returns the existing entry (idempotent)."""
        wl = MagicMock()
        wl.fund_code = "000001"
        wl.fund_name = "Test Fund"
        wl.added_at = datetime(2025, 6, 1)

        _setup_execute_return_scalar_one_or_none(mock_db, wl)

        result = await service.add_to_watchlist("000001", "Already Exists")

        assert result["fund_code"] == "000001"
        assert result["fund_name"] == "Test Fund"  # original name preserved

    async def test_list_watchlist_with_nav(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """List watchlist enriched with NAV from Redis."""
        wl1 = MagicMock()
        wl1.fund_code = "000001"
        wl1.fund_name = "Fund A"
        wl1.added_at = datetime(2025, 6, 1)

        wl2 = MagicMock()
        wl2.fund_code = "000002"
        wl2.fund_name = "Fund B"
        wl2.added_at = datetime(2025, 6, 2)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [wl1, wl2]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Different NAV for each fund
        mock_redis.hgetall.side_effect = [
            {"nav": "1.5000", "daily_return": "0.0100"},
            {"nav": "2.0000", "daily_return": "-0.0050"},
        ]

        result = await service.list_watchlist()

        assert len(result) == 2
        assert result[0]["fund_code"] == "000001"
        assert result[0]["latest_nav"] == Decimal("1.5000")
        assert result[0]["daily_return"] == Decimal("0.0100")
        assert result[1]["fund_code"] == "000002"
        assert result[1]["latest_nav"] == Decimal("2.0000")

    async def test_remove_from_watchlist_success(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Remove existing fund from watchlist."""
        wl = MagicMock()
        wl.fund_code = "000001"
        _setup_execute_return_scalar_one_or_none(mock_db, wl)

        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        result = await service.remove_from_watchlist("000001")

        assert result is True

    async def test_remove_from_watchlist_nonexistent(
        self, service: HoldingService, mock_db: MagicMock, mock_redis: AsyncMock
    ) -> None:
        """Remove non-existent fund returns False."""
        _setup_execute_return_scalar_one_or_none(mock_db, None)

        result = await service.remove_from_watchlist("NONEXIST")

        assert result is False
