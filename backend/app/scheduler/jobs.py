"""
Scheduled jobs for data ingestion, cache refresh, and health monitoring.

Each job creates its own DB session and Redis connection so that
a single failure does not poison subsequent invocations.
"""

import contextlib
import logging
import traceback
from datetime import UTC, date, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.adapters import get_adapter
from app.adapters.base import FundRaw, NavRaw
from app.adapters.normalizer import DataNormalizer
from app.database import async_session
from app.redis_client import get_redis
from app.services.cache_service import CacheService
from app.services.data_ingestion_service import DataIngestionService
from app.utils.cross_validator import CrossValidator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_TRACKED_FUND_CODES: list[str] = [
    "000001",  # 华夏成长混合
    "110022",  # 易方达消费行业
    "161725",  # 招商中证白酒
    "000697",  # 汇添富移动互联
    "002939",  # 广发创新升级
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _today() -> date:
    return date.today()


def _days_ago(n: int) -> date:
    return _today() - timedelta(days=n)


# ---------------------------------------------------------------------------
# Core job: fetch market data
# ---------------------------------------------------------------------------
async def fetch_market_data() -> None:
    """
    Core job: fetch NAV / market data from all adapters.

    1. Get TiantianAdapter + EastmoneyAdapter
    2. Fetch latest NAV for all tracked funds from each source
    3. Normalise data through DataNormalizer
    4. Cross-validate with CrossValidator (log alerts)
    5. Write to PostgreSQL via DataIngestionService
    6. Update Redis cache via CacheService
    """
    logger.info("fetch_market_data: starting cycle")
    normalizer = DataNormalizer()
    validator = CrossValidator()

    # ------------------------------------------------------------------
    # Step 1 & 2 — Fetch NAV from both sources
    # ------------------------------------------------------------------
    adapters = ["tiantian", "eastmoney"]
    raw_navs_by_source: dict[str, list[NavRaw]] = {}

    for source_name in adapters:
        try:
            adapter = get_adapter(source_name)
        except ValueError:
            logger.warning("fetch_market_data: adapter '%s' not available, skipping", source_name)
            continue

        all_raw: list[NavRaw] = []
        for code in _TRACKED_FUND_CODES:
            try:
                navs = await adapter.fetch_nav(
                    fund_code=code,
                    start_date=_days_ago(30),
                    end_date=_today(),
                )
                all_raw.extend(navs)
                logger.debug("Fetched %d NAV records for %s from %s", len(navs), code, source_name)
            except Exception:
                logger.exception(
                    "Failed to fetch NAV for %s from %s", code, source_name
                )

        raw_navs_by_source[source_name] = all_raw
        logger.info(
            "fetch_market_data: %s returned %d total NAV records",
            source_name,
            len(all_raw),
        )

    # ------------------------------------------------------------------
    # Step 3 — Normalise
    # ------------------------------------------------------------------
    normalized_by_source: dict[str, list[NavRaw]] = {}
    for source_name, raw_list in raw_navs_by_source.items():
        try:
            normalized = normalizer.normalize_nav(raw_list, source=source_name)
            normalized_by_source[source_name] = normalized
        except Exception:
            logger.exception("Normalisation failed for source '%s'", source_name)
            normalized_by_source[source_name] = []

    # ------------------------------------------------------------------
    # Step 4 — Cross-validate
    # ------------------------------------------------------------------
    navs_a = normalized_by_source.get("tiantian", [])
    navs_b = normalized_by_source.get("eastmoney", [])
    if navs_a and navs_b:
        try:
            alerts = validator.validate_nav(
                navs_a=navs_a,
                navs_b=navs_b,
                source_a="tiantian",
                source_b="eastmoney",
            )
            if alerts:
                logger.warning(
                    "Cross-validation produced %d alerts for %d / %d records",
                    len(alerts),
                    len(navs_a),
                    len(navs_b),
                )
            else:
                logger.info("Cross-validation: no discrepancies found")
        except Exception:
            logger.exception("Cross-validation failed")

    # ------------------------------------------------------------------
    # Step 5 — Write to PostgreSQL
    # ------------------------------------------------------------------
    async with async_session() as db:
        svc = DataIngestionService(db)

        # Determine which source delivered the most records; prefer it
        primary_source = (
            "tiantian" if len(normalized_by_source.get("tiantian", []))
            >= len(normalized_by_source.get("eastmoney", []))
            else "eastmoney"
        )
        primary_navs = normalized_by_source.get(primary_source, [])

        if primary_navs:
            count = await svc.insert_nav(primary_navs)
            logger.info(
                "Written %d NAV records to DB (primary source: %s)",
                count,
                primary_source,
            )
        else:
            logger.warning("No NAV records to write — both sources empty/failed")

        # Log the fetch to data_source_logs
        for src in adapters:
            raw_count = len(raw_navs_by_source.get(src, []))
            norm_count = len(normalized_by_source.get(src, []))
            logger.info(
                "Source %s: raw=%d normalized=%d",
                src, raw_count, norm_count,
            )
            await svc.log_fetch(
                source_name=src,
                fetch_type="daily_nav",
                status="success" if norm_count > 0 else "partial",
                record_count=norm_count,
            )

    # ------------------------------------------------------------------
    # Step 6 — Update Redis cache
    # ------------------------------------------------------------------
    try:
        redis = await get_redis()
        cache = CacheService(redis)

        # Update latest NAV for each tracked fund
        for code in _TRACKED_FUND_CODES:
            latest: NavRaw | None = None
            for src_records in normalized_by_source.values():
                for n in src_records:
                    if n.fund_code == code and (latest is None or n.date > latest.date):
                        latest = n
            if latest is not None:
                await cache.set_latest_nav(
                    fund_code=code,
                    nav=latest.nav,
                    accumulated_nav=latest.accumulated_nav,
                    daily_return=latest.daily_return,
                )

        # Cache the 30-day NAV for each tracked fund
        for code in _TRACKED_FUND_CODES:
            fund_navs = [
                n for src_records in normalized_by_source.values()
                for n in src_records
                if n.fund_code == code
            ]
            if fund_navs:
                cache_points = DataNormalizer.navs_to_dicts(fund_navs)
                await cache.set_nav_30d(code, cache_points)

        # Set refresh time
        now_iso = datetime.now(UTC).isoformat()
        await cache.set_refresh_time(now_iso)
        logger.info("Redis cache updated — refresh time: %s", now_iso)

    except Exception:
        logger.exception("Redis cache update failed during fetch_market_data")

    logger.info("fetch_market_data: cycle complete")


# ---------------------------------------------------------------------------
# Daily job: sync full fund list
# ---------------------------------------------------------------------------
async def fetch_fund_list_daily() -> None:
    """Daily job (3:00 AM): sync full fund list from all sources."""
    logger.info("fetch_fund_list_daily: starting")
    normalizer = DataNormalizer()

    async with async_session() as db:
        svc = DataIngestionService(db)

        for source_name in ("tiantian", "eastmoney"):
            try:
                adapter = get_adapter(source_name)
            except ValueError:
                logger.warning("Adapter '%s' not found, skipping fund list sync", source_name)
                continue

            try:
                raw_list: list[FundRaw] = await adapter.fetch_fund_list()
                if not raw_list:
                    logger.warning("Empty fund list from %s", source_name)
                    await svc.log_fetch(source_name, "fund_list", "empty", 0)
                    continue

                normalized = normalizer.normalize_fund_list(raw_list, source=source_name)
                count = await svc.upsert_funds(normalized)
                await svc.log_fetch(source_name, "fund_list", "success", count)

                # Update fund list cache
                try:
                    redis = await get_redis()
                    cache = CacheService(redis)
                    cache_list = DataNormalizer.funds_to_dicts(normalized)
                    await cache.set_fund_list(cache_list)
                except Exception:
                    logger.exception("Failed to update fund list cache for %s", source_name)

                logger.info(
                    "fetch_fund_list_daily: %s — %d funds upserted",
                    source_name,
                    count,
                )
            except Exception:
                logger.exception(
                    "fetch_fund_list_daily: failed for source '%s'", source_name
                )
                with contextlib.suppress(Exception):
                    await svc.log_fetch(
                        source_name, "fund_list", "failed", 0,
                        error_message=traceback.format_exc(),
                    )

    logger.info("fetch_fund_list_daily: complete")


# ---------------------------------------------------------------------------
# Daily job: clean old recommendations
# ---------------------------------------------------------------------------
async def clean_old_recommendations() -> None:
    """Daily job (4:00 AM): delete recommendation_logs older than 30 days."""
    logger.info("clean_old_recommendations: starting")
    try:
        async with async_session() as db:
            svc = DataIngestionService(db)
            deleted = await svc.delete_stale_recommendations(cutoff_days=30)
            logger.info("clean_old_recommendations: deleted %d rows", deleted)
    except Exception:
        logger.exception("clean_old_recommendations failed")


# ---------------------------------------------------------------------------
# Periodic health check
# ---------------------------------------------------------------------------
async def health_check_sources() -> None:
    """
    Every 10 minutes: check each adapter's health_check(),
    log failures to data_source_logs.
    """
    logger.debug("health_check_sources: starting")
    async with async_session() as db:
        svc = DataIngestionService(db)
        adapters = ["tiantian", "eastmoney"]

        for name in adapters:
            try:
                adapter = get_adapter(name)
            except ValueError:
                continue

            try:
                ok = await adapter.health_check()
                status = "success" if ok else "failed"
                if not ok:
                    logger.warning("Health check FAILED for adapter '%s'", name)
                else:
                    logger.debug("Health check OK for adapter '%s'", name)
            except Exception:
                status = "failed"
                logger.exception("Health check exception for adapter '%s'", name)

            with contextlib.suppress(Exception):
                await svc.log_fetch(
                    source_name=name,
                    fetch_type="health_check",
                    status=status,
                )

    logger.debug("health_check_sources: complete")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all scheduled jobs on the given scheduler instance."""
    scheduler.add_job(
        fetch_market_data,
        "cron",
        minute="37",
        id="fetch_market_data",
        name="Fetch market data hourly",
    )
    scheduler.add_job(
        fetch_fund_list_daily,
        "cron",
        hour="3",
        minute="0",
        id="fetch_fund_list_daily",
        name="Daily fund list sync at 3:00 AM",
    )
    scheduler.add_job(
        clean_old_recommendations,
        "cron",
        hour="4",
        minute="0",
        id="clean_old_recommendations",
        name="Clean old recommendations at 4:00 AM",
    )
    scheduler.add_job(
        health_check_sources,
        "interval",
        minutes=10,
        id="health_check_sources",
        name="Health check data sources every 10 min",
    )
    logger.info("Scheduler jobs registered: %d jobs", 4)
