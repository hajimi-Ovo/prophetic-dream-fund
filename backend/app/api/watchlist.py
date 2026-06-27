"""
Watchlist API routes.

All endpoints return the unified ``{code, message, data}`` format.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_redis
from app.schemas.holding import WatchlistCreate
from app.services.holding_service import HoldingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

ERR_INVALID_CODE = 10002


# ---------------------------------------------------------------------------
# GET /watchlist
# ---------------------------------------------------------------------------
@router.get("")
async def list_watchlist(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """List all funds in the watchlist with latest NAV data."""
    service = HoldingService(db, redis)
    items = await service.list_watchlist()
    return {
        "code": 0,
        "message": "ok",
        "data": {"items": items},
    }


# ---------------------------------------------------------------------------
# POST /watchlist
# ---------------------------------------------------------------------------
@router.post("", status_code=201)
async def add_to_watchlist(
    data: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Add a fund to the watchlist.

    Returns existing entry if the fund is already on the watchlist (idempotent).
    """
    service = HoldingService(db, redis)
    item = await service.add_to_watchlist(data.fund_code, data.fund_name)
    return {
        "code": 0,
        "message": "ok",
        "data": item,
    }


# ---------------------------------------------------------------------------
# DELETE /watchlist/{fund_code}
# ---------------------------------------------------------------------------
@router.delete("/{fund_code}")
async def remove_from_watchlist(
    fund_code: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Remove a fund from the watchlist by its fund code."""
    service = HoldingService(db, redis)
    removed = await service.remove_from_watchlist(fund_code)
    if not removed:
        return {
            "code": ERR_INVALID_CODE,
            "message": f"Watchlist item not found: {fund_code}",
            "data": None,
        }
    return {
        "code": 0,
        "message": "ok",
        "data": None,
    }
