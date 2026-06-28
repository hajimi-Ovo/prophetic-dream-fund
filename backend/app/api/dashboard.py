"""
Dashboard API routes.

All endpoints return the unified ``{code, message, data}`` format.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# GET /dashboard/summary
# ---------------------------------------------------------------------------
@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get dashboard summary: total asset, profit, today profit, holding count."""
    service = DashboardService(db)
    result = await service.get_summary()
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }


# ---------------------------------------------------------------------------
# GET /dashboard/returns-chart
# ---------------------------------------------------------------------------
@router.get("/returns-chart")
async def get_returns_chart(
    period: str = Query(
        default="1m",
        description="Chart period: 1m, 3m, 6m, 1y, all",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get cumulative returns curve with optional benchmark comparison."""
    service = DashboardService(db)
    result = await service.get_returns_chart(period)
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }


# ---------------------------------------------------------------------------
# GET /dashboard/allocation
# ---------------------------------------------------------------------------
@router.get("/allocation")
async def get_allocation(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get portfolio allocation breakdown grouped by fund type."""
    service = DashboardService(db)
    result = await service.get_allocation()
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }


# ---------------------------------------------------------------------------
# GET /dashboard/risk-metrics
# ---------------------------------------------------------------------------
@router.get("/risk-metrics")
async def get_risk_metrics(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get portfolio-level risk metrics: max drawdown, Sharpe ratio, volatility."""
    service = DashboardService(db)
    result = await service.get_risk_metrics()
    return {
        "code": 0,
        "message": "ok",
        "data": result,
    }
