"""
Recommendation (智能推荐) API routes.

All endpoints return the unified ``{code, message, data}`` format.

Error codes: 30001-30099 (recommendation module).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.schemas.recommendation import RiskAssessmentRequest
from app.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommend", tags=["recommendations"])


def _serialize_decimals(obj: Any) -> Any:
    """Recursively convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _serialize_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_serialize_decimals(v) for v in obj]
    return obj


# ============================================================================
# Risk Assessment — POST & GET
# ============================================================================
@router.post("/risk-assessment")
async def save_risk_assessment(
    body: RiskAssessmentRequest,
    user_id: int | None = Query(default=None, description="Owner user ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Save or update user risk profile and return suggested allocation."""
    service = RecommendationService(db)
    try:
        result = await service.save_risk_assessment(
            body.model_dump(), user_id=user_id
        )
        return {"code": 0, "message": "ok", "data": result}
    except Exception as exc:
        logger.exception("Failed to save risk assessment")
        return {
            "code": 30001,
            "message": f"Failed to save risk assessment: {exc}",
            "data": None,
        }


@router.get("/risk-assessment")
async def get_risk_assessment(
    user_id: int | None = Query(default=None, description="Owner user ID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the latest risk profile for a user."""
    service = RecommendationService(db)
    try:
        result = await service.get_risk_assessment(user_id=user_id)
        if result is None:
            return {
                "code": 30002,
                "message": "No risk assessment found",
                "data": None,
            }
        return {"code": 0, "message": "ok", "data": result}
    except Exception as exc:
        logger.exception("Failed to get risk assessment")
        return {
            "code": 30003,
            "message": f"Failed to get risk assessment: {exc}",
            "data": None,
        }


# ============================================================================
# Recommended Funds
# ============================================================================
@router.get("/funds")
async def get_recommended_funds(
    strategy: str = Query(
        default="hybrid",
        description="Strategy: hybrid, value, growth",
    ),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    risk_tolerance: str = Query(
        default="moderate",
        description="Override risk tolerance: conservative, moderate, aggressive",
    ),
    investment_horizon: str = Query(
        default="medium",
        description="Override investment horizon: short, medium, long, very_long",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get ranked fund recommendations based on risk profile."""
    service = RecommendationService(db)
    try:
        profile: dict[str, Any] = {
            "risk_tolerance": risk_tolerance,
            "investment_horizon": investment_horizon,
            "return_expectation": "balanced",
        }
        result = await service.get_recommended_funds(
            profile, strategy=strategy, limit=limit
        )
        return {"code": 0, "message": "ok", "data": result}
    except Exception as exc:
        logger.exception("Failed to get recommended funds")
        return {
            "code": 30010,
            "message": f"Failed to get recommendations: {exc}",
            "data": None,
        }


# ============================================================================
# Timing Advice
# ============================================================================
@router.get("/timing/{fund_code}")
async def get_timing_advice(
    fund_code: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get valuation-based timing advice for a fund."""
    service = RecommendationService(db)
    try:
        result = await service.get_timing_advice(fund_code)
        return {"code": 0, "message": "ok", "data": result}
    except Exception as exc:
        logger.exception("Failed to get timing advice for %s", fund_code)
        return {
            "code": 30020,
            "message": f"Failed to get timing advice: {exc}",
            "data": None,
        }


# ============================================================================
# Amount Advice
# ============================================================================
@router.get("/amount")
async def get_amount_advice(
    risk_tolerance: str = Query(
        default="moderate",
        description="Risk tolerance: conservative, moderate, aggressive",
    ),
    investment_horizon: str = Query(
        default="medium",
        description="Investment horizon: short, medium, long, very_long",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get suggested investment amount based on risk profile."""
    service = RecommendationService(db)
    try:
        profile: dict[str, Any] = {
            "risk_tolerance": risk_tolerance,
            "investment_horizon": investment_horizon,
        }
        result = await service.get_amount_advice(profile)
        return {"code": 0, "message": "ok", "data": result}
    except Exception as exc:
        logger.exception("Failed to get amount advice")
        return {
            "code": 30030,
            "message": f"Failed to get amount advice: {exc}",
            "data": None,
        }


# ============================================================================
# Portfolio Plan
# ============================================================================
@router.get("/portfolio")
async def get_portfolio_plan(
    total_amount: float = Query(
        default=50000, ge=0, description="Total amount to allocate in CNY"
    ),
    risk_tolerance: str = Query(
        default="moderate",
        description="Risk tolerance: conservative, moderate, aggressive",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Build an optimized portfolio allocation plan."""
    service = RecommendationService(db)
    try:
        profile: dict[str, Any] = {"risk_tolerance": risk_tolerance}
        result = await service.get_portfolio_plan(
            profile, total_amount=Decimal(str(total_amount))
        )
        # Convert Decimal values to serializable types (float for JSON)
        result = _serialize_decimals(result)
        return {"code": 0, "message": "ok", "data": result}
    except Exception as exc:
        logger.exception("Failed to build portfolio plan")
        return {
            "code": 30040,
            "message": f"Failed to build portfolio plan: {exc}",
            "data": None,
        }


# ============================================================================
# Backtest
# ============================================================================
@router.get("/backtest")
async def get_backtest(
    strategy: str = Query(
        default="hybrid",
        description="Strategy: hybrid, value, growth",
    ),
    period: str = Query(
        default="3y",
        description="Backtest period: 1y, 3y, 5y",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run a historical strategy backtest."""
    service = RecommendationService(db)
    try:
        result = await service.get_backtest(strategy=strategy, period=period)
        return {"code": 0, "message": "ok", "data": result}
    except Exception as exc:
        logger.exception("Failed to run backtest")
        return {
            "code": 30050,
            "message": f"Failed to run backtest: {exc}",
            "data": None,
        }
