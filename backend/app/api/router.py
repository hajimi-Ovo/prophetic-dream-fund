"""
API router for /api/v1.

Aggregates all sub-routers and exposes a health-check endpoint.
"""

from typing import Any

from fastapi import APIRouter

from app.api.dashboard import router as dashboard_router
from app.api.data_mgmt import router as data_router
from app.api.funds import router as funds_router
from app.api.holdings import router as holdings_router
from app.api.ocr import router as ocr_router
from app.api.recommendations import router as recommend_router
from app.api.watchlist import router as watchlist_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(data_router)
api_router.include_router(funds_router)
api_router.include_router(holdings_router)
api_router.include_router(ocr_router)
api_router.include_router(recommend_router)
api_router.include_router(watchlist_router)
api_router.include_router(dashboard_router)


@api_router.get("/")
async def api_health() -> dict[str, Any]:
    """API-level health check."""
    return {
        "code": 0,
        "message": "ok",
        "data": {"service": "prophetic-dream-fund"},
    }
