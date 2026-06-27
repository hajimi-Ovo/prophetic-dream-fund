"""
Holdings CRUD API routes.

All endpoints return the unified ``{code, message, data}`` format.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_redis
from app.schemas.holding import HoldingCreate, HoldingUpdate
from app.services.holding_service import HoldingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holdings", tags=["holdings"])

# Error codes
ERR_HOLDING_NOT_FOUND = 10001
ERR_INVALID_CODE = 10002


# ---------------------------------------------------------------------------
# POST /holdings
# ---------------------------------------------------------------------------
@router.post("", status_code=201)
async def create_holding(
    data: HoldingCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Create a new holding and record the initial buy transaction."""
    service = HoldingService(db, redis)
    holding = await service.create(data)
    return {
        "code": 0,
        "message": "ok",
        "data": holding,
    }


# ---------------------------------------------------------------------------
# GET /holdings
# ---------------------------------------------------------------------------
@router.get("")
async def list_holdings(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """List all holdings with real-time profit/loss calculations."""
    service = HoldingService(db, redis)
    result = await service.list_with_profit()
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "items": result["items"],
            "summary": result["summary"],
        },
    }


# ---------------------------------------------------------------------------
# GET /holdings/{id}
# ---------------------------------------------------------------------------
@router.get("/{id}")
async def get_holding(
    id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Get a single holding with real-time P&L details."""
    service = HoldingService(db, redis)
    holding = await service.get(id)
    if holding is None:
        return {
            "code": ERR_HOLDING_NOT_FOUND,
            "message": f"Holding not found: {id}",
            "data": None,
        }
    return {
        "code": 0,
        "message": "ok",
        "data": holding,
    }


# ---------------------------------------------------------------------------
# PUT /holdings/{id}
# ---------------------------------------------------------------------------
@router.put("/{id}")
async def update_holding(
    id: int,
    data: HoldingUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Update a holding. Fund code cannot be changed after creation."""
    service = HoldingService(db, redis)
    holding = await service.update(id, data)
    if holding is None:
        return {
            "code": ERR_HOLDING_NOT_FOUND,
            "message": f"Holding not found: {id}",
            "data": None,
        }
    return {
        "code": 0,
        "message": "ok",
        "data": holding,
    }


# ---------------------------------------------------------------------------
# DELETE /holdings/{id}
# ---------------------------------------------------------------------------
@router.delete("/{id}")
async def delete_holding(
    id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Delete a holding and cascade to related transactions."""
    service = HoldingService(db, redis)
    deleted = await service.delete(id)
    if not deleted:
        return {
            "code": ERR_HOLDING_NOT_FOUND,
            "message": f"Holding not found: {id}",
            "data": None,
        }
    return {
        "code": 0,
        "message": "ok",
        "data": None,
    }
