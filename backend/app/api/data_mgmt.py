"""
Data management API — endpoints for data source status, cache refresh,
manual trigger, and cross-validation reports.

All responses use the unified ``{code, message, data}`` format.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from app.adapters import ADAPTER_REGISTRY, get_adapter
from app.services.cache_service import get_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data-management"])


# ---------------------------------------------------------------------------
# GET /data/sources — list all configured data sources
# ---------------------------------------------------------------------------
@router.get("/sources")
async def list_data_sources() -> dict[str, Any]:
    """Return status of all configured data sources."""
    sources: list[dict[str, Any]] = []

    for name in ADAPTER_REGISTRY:
        source_info: dict[str, Any] = {
            "name": name,
            "status": "unknown",
            "last_checked": None,
        }
        try:
            adapter = get_adapter(name)
            is_healthy = await adapter.health_check()
            source_info["status"] = "healthy" if is_healthy else "unhealthy"
            source_info["last_checked"] = datetime.now(UTC).isoformat()
        except Exception:
            source_info["status"] = "error"
            logger.exception("Health check failed for %s during /data/sources", name)

        sources.append(source_info)

    return {
        "code": 0,
        "message": "ok",
        "data": {"sources": sources},
    }


# ---------------------------------------------------------------------------
# GET /data/refresh-status — last refresh time and data completeness
# ---------------------------------------------------------------------------
@router.get("/refresh-status")
async def get_refresh_status() -> dict[str, Any]:
    """Return last refresh time and known data gaps."""
    cache = get_cache()
    refresh_time = await cache.get_refresh_time()

    data: dict[str, Any] = {
        "last_refresh": refresh_time,
        "data_gaps": [],  # placeholder — could query DB for missing NAV dates
    }

    return {
        "code": 0,
        "message": "ok",
        "data": data,
    }


# ---------------------------------------------------------------------------
# POST /data/trigger-refresh — manual market data refresh
# ---------------------------------------------------------------------------
@router.post("/trigger-refresh")
async def trigger_refresh() -> dict[str, Any]:
    """Manually trigger market data refresh (for debugging / ops)."""
    from app.scheduler.jobs import fetch_market_data

    try:
        await fetch_market_data()
        return {
            "code": 0,
            "message": "Refresh triggered successfully",
            "data": None,
        }
    except Exception as exc:
        logger.exception("Manual trigger-refresh failed")
        return {
            "code": -1,
            "message": f"Refresh failed: {exc!s}",
            "data": None,
        }


# ---------------------------------------------------------------------------
# GET /data/cross-validation — latest validation report
# ---------------------------------------------------------------------------
@router.get("/cross-validation")
async def get_cross_validation_report() -> dict[str, Any]:
    """Return recent cross-validation alerts between data sources."""
    from app.utils.cross_validator import CrossValidator

    # The validator holds alerts in-memory from the last validation cycle.
    # In a production deployment this would be backed by a persistent store.
    # We create a fresh instance here because the scheduled job uses its own
    # instance.  For a real report we would query a database table.
    # For now, trigger a lightweight comparison on demand.
    try:
        tiantian = get_adapter("tiantian")
        eastmoney = get_adapter("eastmoney")
    except ValueError:
        return {
            "code": 0,
            "message": "ok",
            "data": {
                "alerts": [],
                "note": "One or more adapters are not available",
            },
        }

    validator = CrossValidator()
    from datetime import date, timedelta

    today = date.today()
    week_ago = today - timedelta(days=7)

    # Compare NAV for a sample of funds
    sample_codes = ["000001", "110022", "161725"]
    all_alerts: list[dict[str, Any]] = []

    for code in sample_codes:
        try:
            navs_a = await tiantian.fetch_nav(code, week_ago, today)
            navs_b = await eastmoney.fetch_nav(code, week_ago, today)

            if navs_a and navs_b:
                alerts = validator.validate_nav(
                    navs_a=navs_a,
                    navs_b=navs_b,
                    source_a="tiantian",
                    source_b="eastmoney",
                )
                for alert in alerts:
                    all_alerts.append({
                        "source_a": alert.source_a,
                        "source_b": alert.source_b,
                        "field": alert.field_name,
                        "fund_code": alert.fund_code,
                        "value_a": str(alert.value_a) if alert.value_a else None,
                        "value_b": str(alert.value_b) if alert.value_b else None,
                        "difference": str(alert.difference) if alert.difference else None,
                        "timestamp": alert.timestamp.isoformat(),
                    })
        except Exception:
            logger.exception("Cross-validation sampling failed for %s", code)

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "alerts": all_alerts,
            "samples_checked": len(sample_codes),
        },
    }
