"""
Data ingestion service — writes normalized data into PostgreSQL.

Uses SQLAlchemy 2.0 async patterns with INSERT … ON CONFLICT handling.
Every batch is committed independently; errors are logged gracefully.
"""

import logging
from datetime import UTC
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import FundDetailRaw, FundHoldingRaw, FundRaw, NavRaw
from app.models.data_source import DataSourceLog
from app.models.fund import Fund, FundHolding, FundManager, FundNav

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DataIngestionService:
    """Writes normalized raw data to the database via async SQLAlchemy."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Fund upsert
    # ------------------------------------------------------------------
    async def upsert_funds(self, funds: list[FundRaw]) -> int:
        """
        UPSERT fund basic info using ``INSERT … ON CONFLICT (code) DO UPDATE``.

        Returns the number of rows affected.
        """
        if not funds:
            logger.info("upsert_funds: empty list, nothing to do")
            return 0

        rows: list[dict[str, Any]] = []
        for f in funds:
            rows.append({
                "code": f.code,
                "name": f.name,
                "type": f.type,
                "scale": f.scale,
                "fee_rate": f.fee_rate,
                "company": f.company,
                "inception_date": f.inception_date,
            })

        count = 0
        try:
            stmt = (
                pg_insert(Fund)
                .values(rows)
                .on_conflict_do_update(
                    index_elements=[Fund.code],
                    set_={
                        "name": pg_insert(Fund).excluded.name,
                        "type": pg_insert(Fund).excluded.type,
                        "scale": pg_insert(Fund).excluded.scale,
                        "fee_rate": pg_insert(Fund).excluded.fee_rate,
                        "company": pg_insert(Fund).excluded.company,
                        "inception_date": pg_insert(Fund).excluded.inception_date,
                    },
                )
            )
            result = await self.db.execute(stmt)
            await self.db.commit()
            count = result.rowcount if result.rowcount else 0
            logger.info("upsert_funds: %d records upserted", count)
        except Exception:
            await self.db.rollback()
            logger.exception("upsert_funds failed")
        return count

    # ------------------------------------------------------------------
    # NAV insert
    # ------------------------------------------------------------------
    async def insert_nav(self, nav_list: list[NavRaw]) -> int:
        """
        Insert NAV data with ``ON CONFLICT (fund_code, date) DO NOTHING``.

        Returns count of newly inserted rows.
        """
        if not nav_list:
            return 0

        rows: list[dict[str, Any]] = []
        for n in nav_list:
            rows.append({
                "fund_code": n.fund_code,
                "date": n.date,
                "nav": n.nav,
                "accumulated_nav": n.accumulated_nav,
                "daily_return": n.daily_return,
            })

        count = 0
        try:
            stmt = (
                pg_insert(FundNav)
                .values(rows)
                .on_conflict_do_nothing(
                    index_elements=[FundNav.fund_code, FundNav.date],
                )
            )
            result = await self.db.execute(stmt)
            await self.db.commit()
            count = result.rowcount if result.rowcount else 0
            logger.info("insert_nav: %d new records inserted", count)
        except Exception:
            await self.db.rollback()
            logger.exception("insert_nav failed")
        return count

    # ------------------------------------------------------------------
    # Fund holdings upsert
    # ------------------------------------------------------------------
    async def upsert_fund_holdings(self, holdings: list[FundHoldingRaw]) -> int:
        """
        UPSERT fund holdings.

        ``ON CONFLICT (fund_code, report_date, stock_code) DO UPDATE``
        so subsequent reports for the same fund/quarter update existing rows.
        """
        if not holdings:
            return 0

        rows: list[dict[str, Any]] = []
        for h in holdings:
            rows.append({
                "fund_code": h.fund_code,
                "report_date": h.report_date,
                "stock_code": h.stock_code,
                "stock_name": h.stock_name,
                "ratio": h.ratio,
            })

        count = 0
        try:
            stmt = (
                pg_insert(FundHolding)
                .values(rows)
                .on_conflict_do_update(
                    index_elements=[
                        FundHolding.fund_code,
                        FundHolding.report_date,
                        FundHolding.stock_code,
                    ],
                    set_={
                        "stock_name": pg_insert(FundHolding).excluded.stock_name,
                        "ratio": pg_insert(FundHolding).excluded.ratio,
                    },
                )
            )
            result = await self.db.execute(stmt)
            await self.db.commit()
            count = result.rowcount if result.rowcount else 0
            logger.info("upsert_fund_holdings: %d records upserted", count)
        except Exception:
            await self.db.rollback()
            logger.exception("upsert_fund_holdings failed")
        return count

    # ------------------------------------------------------------------
    # Fund managers upsert
    # ------------------------------------------------------------------
    async def upsert_fund_managers(self, managers: list[FundDetailRaw]) -> int:
        """
        UPSERT fund managers extracted from FundDetailRaw.

        Uses ``ON CONFLICT (fund_code, name) DO UPDATE``.  (There is no unique
        constraint on (fund_code, name) in the schema as written, so we use a
        different approach: delete existing managers for each fund_code and
        insert fresh to keep things simple and correct.)
        """
        if not managers:
            return 0

        rows: list[dict[str, Any]] = []
        fund_codes: set[str] = set()
        for d in managers:
            if not d.manager_name:
                continue
            fund_codes.add(d.code)
            rows.append({
                "fund_code": d.code,
                "name": d.manager_name,
                "start_date": d.manager_start_date,
                "tenure_return": d.manager_tenure_return,
            })

        if not rows:
            return 0

        count = 0
        try:
            # Delete old managers for funds we are about to update
            for code in fund_codes:
                await self.db.execute(
                    delete(FundManager).where(FundManager.fund_code == code)
                )
            await self.db.flush()

            # Insert fresh
            stmt = pg_insert(FundManager).values(rows)
            result = await self.db.execute(stmt)
            await self.db.commit()
            count = result.rowcount if result.rowcount else 0
            logger.info("upsert_fund_managers: %d records inserted", count)
        except Exception:
            await self.db.rollback()
            logger.exception("upsert_fund_managers failed")
        return count

    # ------------------------------------------------------------------
    # Data-source log
    # ------------------------------------------------------------------
    async def log_fetch(
        self,
        source_name: str,
        fetch_type: str,
        status: str,
        record_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Write a DataSourceLog entry for observability."""
        try:
            log_entry = DataSourceLog(
                source_name=source_name,
                fetch_type=fetch_type,
                status=status,
                record_count=record_count,
                error_message=error_message,
            )
            self.db.add(log_entry)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to write DataSourceLog for %s/%s", source_name, fetch_type)

    # ------------------------------------------------------------------
    # Helpers for scheduled tasks
    # ------------------------------------------------------------------
    async def get_tracked_fund_codes(self) -> list[str]:
        """Return all fund codes currently stored in the DB."""
        try:
            result = await self.db.execute(select(Fund.code))
            return [row[0] for row in result.fetchall()]
        except Exception:
            logger.exception("Failed to query tracked fund codes")
            return []

    async def delete_stale_recommendations(self, cutoff_days: int = 30) -> int:
        """Delete recommendation_logs older than *cutoff_days* days."""
        from datetime import datetime, timedelta

        from app.models.recommendation import RecommendationLog

        cutoff = datetime.now(UTC) - timedelta(days=cutoff_days)
        try:
            stmt = delete(RecommendationLog).where(RecommendationLog.created_at < cutoff)
            result = await self.db.execute(stmt)
            await self.db.commit()
            count = result.rowcount if result.rowcount else 0
            logger.info("Deleted %d stale recommendation logs", count)
            return count
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to delete stale recommendations")
            return 0
