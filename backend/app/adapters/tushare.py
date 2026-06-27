"""
Tushare data-source adapter stub.

Requires TUSHARE_TOKEN environment variable for API access.
Provides fund data via the tushare Pro API (https://tushare.pro).
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from app.adapters.base import (
    BaseAdapter,
    FundDetailRaw,
    FundHoldingRaw,
    FundRaw,
    NavRaw,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _safe_decimal(value: object) -> Decimal | None:
    """Convert *value* to Decimal, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return Decimal(str(value))
    s = str(value).strip()
    if s in ("", "--", "nan", "NaN"):
        return None
    try:
        return Decimal(s.replace(",", "").replace("%", ""))
    except Exception:
        return None


def _safe_date(value: object) -> date | None:
    """Parse a date string, returning None on failure."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _get_token() -> str | None:
    """Retrieve Tushare API token from environment."""
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        logger.warning("TUSHARE_TOKEN environment variable is not set")
    return token


class TushareAdapter(BaseAdapter):
    """
    Data adapter for Tushare Pro (https://tushare.pro).

    Requires ``TUSHARE_TOKEN`` env var for API access.  All methods
    return empty results when the token is missing or API calls fail.
    """

    @property
    def source_name(self) -> str:
        return "tushare"

    @property
    def _base_url(self) -> str:
        return "https://api.tushare.pro/"

    @property
    def requires_auth(self) -> bool:
        """Indicates that this adapter needs an API token."""
        return True

    # -- Fund list ----------------------------------------------------------

    async def fetch_fund_list(self) -> list[FundRaw]:
        """
        Fetch fund list from Tushare.

        Uses ``fund_basic`` interface.  Returns empty list if token is
        missing or the API call fails.
        """
        results: list[FundRaw] = []
        token = _get_token()
        if not token:
            return results

        try:
            import tushare as ts  # type: ignore[import-untyped]

            pro = ts.pro_api(token)
            df = pro.fund_basic(market="E")
            if df is None or df.empty:
                logger.warning("Tushare: fund list returned empty")
                return results

            for _, row in df.iterrows():
                try:
                    code = str(row.get("ts_code", "")).split(".")[0] if "ts_code" in df.columns else str(row.get("fund_code", ""))
                    code = code.strip().zfill(6)
                    name = str(row.get("name", ""))
                    fund_type = str(row.get("fund_type", "other")).lower()
                    scale = _safe_decimal(row.get("fund_size", None))

                    results.append(
                        FundRaw(
                            code=code,
                            name=name,
                            type=fund_type if fund_type else "other",
                            scale=scale,
                        )
                    )
                except Exception:
                    continue

        except ImportError:
            logger.debug("Tushare library not installed — returning empty fund list")
        except Exception:
            logger.exception("Tushare: fund list fetch failed")

        logger.info("Tushare: fetched %d funds", len(results))
        return results

    # -- NAV history --------------------------------------------------------

    async def fetch_nav(
        self, fund_code: str, start_date: date, end_date: date
    ) -> list[NavRaw]:
        """
        Fetch NAV history from Tushare.

        Uses ``fund_nav`` interface.
        """
        results: list[NavRaw] = []
        token = _get_token()
        if not token:
            return results

        try:
            import tushare as ts  # type: ignore[import-untyped]

            pro = ts.pro_api(token)
            df = pro.fund_nav(
                ts_code=f"{fund_code}.OF",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                logger.warning("Tushare: NAV history empty for %s", fund_code)
                return results

            for _, row in df.iterrows():
                try:
                    nav_date = _safe_date(row.get("nav_date", row.get("end_date", "")))
                    nav = _safe_decimal(row.get("unit_nav", None))
                    if nav_date is None or nav is None:
                        continue
                    acc = _safe_decimal(row.get("accum_nav", None))
                    # Tushare fund_nav: "nav_return" field for daily return, fallback to "adj_nav"
                    dr_raw = row.get("nav_return", None)
                    if dr_raw is None:
                        dr_raw = row.get("adj_nav", None)
                    dr = _safe_decimal(dr_raw)

                    results.append(
                        NavRaw(
                            fund_code=fund_code,
                            date=nav_date,
                            nav=nav,
                            accumulated_nav=acc,
                            daily_return=dr,
                        )
                    )
                except Exception:
                    continue

        except ImportError:
            logger.debug("Tushare library not installed — returning empty NAV list")
        except Exception:
            logger.exception("Tushare: NAV fetch failed for %s", fund_code)

        logger.info(
            "Tushare: fetched %d NAV records for %s (%s → %s)",
            len(results),
            fund_code,
            start_date,
            end_date,
        )
        return results

    # -- Fund detail --------------------------------------------------------

    async def fetch_fund_detail(self, fund_code: str) -> FundDetailRaw | None:
        """
        Fetch fund metadata from Tushare.

        Uses ``fund_basic`` interface for detailed info.
        """
        token = _get_token()
        if not token:
            return None

        try:
            import tushare as ts  # type: ignore[import-untyped]

            pro = ts.pro_api(token)
            df = pro.fund_basic(ts_code=f"{fund_code}.OF")
            if df is None or df.empty:
                logger.warning("Tushare: no detail info for %s", fund_code)
                return None

            row = df.iloc[0]

            scale = _safe_decimal(row.get("fund_size", None))
            # Management fee from fund_basic
            fee_rate = _safe_decimal(row.get("m_fee", None))
            company = str(row.get("management", "")) or None
            manager_name = str(row.get("fund_manager", "")) or None

            return FundDetailRaw(
                code=fund_code,
                scale=scale,
                fee_rate=fee_rate,
                company=company,
                manager_name=manager_name,
                manager_start_date=None,
                manager_tenure_return=None,
            )

        except ImportError:
            logger.debug("Tushare library not installed — returning empty detail")
        except Exception:
            logger.exception("Tushare: detail fetch failed for %s", fund_code)

        return None

    # -- Holdings -----------------------------------------------------------

    async def fetch_fund_holdings(self, fund_code: str) -> list[FundHoldingRaw]:
        """
        Fetch top-holdings from Tushare.

        Uses ``fund_portfolio`` interface.
        """
        results: list[FundHoldingRaw] = []
        token = _get_token()
        if not token:
            return results

        try:
            import tushare as ts  # type: ignore[import-untyped]

            pro = ts.pro_api(token)
            df = pro.fund_portfolio(ts_code=f"{fund_code}.OF")
            if df is None or df.empty:
                logger.warning("Tushare: no holdings for %s", fund_code)
                return results

            for _, row in df.iterrows():
                try:
                    stock_code = str(row.get("symbol", "")).strip()
                    stock_name = str(row.get("name", "")).strip()
                    ratio = _safe_decimal(row.get("ratio", row.get("mkv", None)))
                    report_date = _safe_date(row.get("end_date", "")) or date.today()

                    if not stock_code:
                        continue

                    results.append(
                        FundHoldingRaw(
                            fund_code=fund_code,
                            report_date=report_date,
                            stock_code=stock_code.zfill(6),
                            stock_name=stock_name or None,
                            ratio=ratio,
                        )
                    )
                except Exception:
                    continue

        except ImportError:
            logger.debug("Tushare library not installed — returning empty holdings")
        except Exception:
            logger.exception("Tushare: holdings fetch failed for %s", fund_code)

        if not results:
            logger.warning("Tushare: no holdings parsed for %s", fund_code)
        else:
            logger.info("Tushare: fetched %d holdings for %s", len(results), fund_code)

        return results
