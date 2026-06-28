"""
Fund market (行情) API routes.

All endpoints return the unified ``{code, message, data}`` format.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.schemas.fund import (
    FundFilterParams,
    SortOrder,
)
from app.services.fund_service import FundService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/funds", tags=["funds"])


# ---------------------------------------------------------------------------
# GET /funds/search
# ---------------------------------------------------------------------------
@router.get("/search")
async def search_funds(
    keyword: str = Query(default="", description="Fuzzy search by code or name"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fuzzy search funds by code or name."""
    service = FundService(db)
    result = await service.search(keyword=keyword, page=page, page_size=page_size)
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "items": result["items"],
            "total": result["total"],
            "page": page,
            "page_size": page_size,
        },
    }


# ---------------------------------------------------------------------------
# GET /funds/filter
# ---------------------------------------------------------------------------
@router.get("/filter")
async def filter_funds(
    type: str | None = Query(default=None, description="Fund type filter"),
    min_scale: float | None = Query(default=None, description="Min AUM/scale"),
    max_scale: float | None = Query(default=None, description="Max AUM/scale"),
    max_fee: float | None = Query(default=None, description="Max management fee rate"),
    manager: str | None = Query(default=None, description="Manager name (fuzzy)"),
    company: str | None = Query(default=None, description="Company name (fuzzy)"),
    sort_by: str | None = Query(
        default=None,
        description="Sort field: latest_nav, daily_return, one_year_return, three_year_return",
    ),
    order: SortOrder = Query(default=SortOrder.DESC, description="Sort direction"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Multi-dimension fund filtering with sort and pagination."""
    from decimal import Decimal

    from app.schemas.fund import FundSortBy

    # Build filter params
    sort_by_enum = FundSortBy(sort_by) if sort_by else None
    params = FundFilterParams(
        type=type,
        min_scale=Decimal(str(min_scale)) if min_scale is not None else None,
        max_scale=Decimal(str(max_scale)) if max_scale is not None else None,
        max_fee=Decimal(str(max_fee)) if max_fee is not None else None,
        manager=manager,
        company=company,
        sort_by=sort_by_enum,
        order=order,
        page=page,
        page_size=page_size,
    )

    service = FundService(db)
    result = await service.filter_funds(params)
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "items": result["items"],
            "total": result["total"],
            "page": page,
            "page_size": page_size,
        },
    }


# ---------------------------------------------------------------------------
# GET /funds/compare — MUST be defined before /{code} to avoid route capture
# ---------------------------------------------------------------------------
@router.get("/compare")
async def compare_funds(
    codes: str = Query(..., description="Comma-separated fund codes, e.g. 000001,110022"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Multi-fund side-by-side comparison with chart overlay data."""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list:
        return {
            "code": -1,
            "message": "No valid fund codes provided",
            "data": None,
        }

    service = FundService(db)
    result = await service.compare(code_list)
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }


# ---------------------------------------------------------------------------
# GET /funds/{code}
# ---------------------------------------------------------------------------
@router.get("/{code}")
async def get_fund_detail(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get full fund detail including NAV, manager, and risk metrics."""
    service = FundService(db)
    detail = await service.get_detail(code)
    if not detail:
        return {
            "code": 404,
            "message": f"Fund not found: {code}",
            "data": None,
        }
    return {
        "code": 0,
        "message": "ok",
        "data": detail,
    }


# ---------------------------------------------------------------------------
# GET /funds/{code}/nav-history
# ---------------------------------------------------------------------------
@router.get("/{code}/nav-history")
async def get_nav_history(
    code: str,
    period: str = Query(default="1m", description="Period: 1m, 3m, 6m, 1y, all"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get NAV history for a fund over a given period."""
    service = FundService(db)
    result = await service.get_nav_history(code, period)
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }


# ---------------------------------------------------------------------------
# GET /funds/{code}/portfolio
# ---------------------------------------------------------------------------
@router.get("/{code}/portfolio")
async def get_portfolio(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get fund's top holdings (重仓股明细)."""
    service = FundService(db)
    holdings = await service.get_portfolio(code)
    return {
        "code": 0,
        "message": "ok",
        "data": {"items": holdings},
    }
