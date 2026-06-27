"""
AKShare data-source adapter.

Provides a third data source via the akshare Python library.
All methods wrap calls in try/except and gracefully degrade when
akshare is not installed or API calls fail.
"""

from __future__ import annotations

import logging
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
    """Convert *value* to Decimal, returning None on failure or empty string."""
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
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


class AKShareAdapter(BaseAdapter):
    """Data adapter for AKShare (https://pypi.org/project/akshare/)."""

    @property
    def source_name(self) -> str:
        return "akshare"

    @property
    def _base_url(self) -> str:
        # AKShare is a library, not an HTTP API, but we provide a
        # homespun health-check target.
        return "https://pypi.org/pypi/akshare/json"

    # -- Fund list ----------------------------------------------------------

    async def fetch_fund_list(self) -> list[FundRaw]:
        """
        Fetch all available funds from AKShare.

        Uses ``akshare.fund_info_index_em`` if available; otherwise
        returns empty list.
        """
        results: list[FundRaw] = []
        try:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.fund_info_index_em("全部")
            if df is None or df.empty:
                logger.warning("AKShare: fund list returned empty DataFrame")
                return results

            for _, row in df.iterrows():
                try:
                    code = str(row.get("基金代码", "")).strip().zfill(6)
                    name = str(row.get("基金简称", "")) if "基金简称" in df.columns else str(row.get("基金名称", ""))
                    cn_type = str(row.get("基金类型", "")) if "基金类型" in df.columns else "other"
                    scale_raw = row.get("基金规模", None)

                    scale = _safe_decimal(scale_raw)

                    results.append(
                        FundRaw(
                            code=code,
                            name=name,
                            type=cn_type.lower() if cn_type else "other",
                            scale=scale,
                        )
                    )
                except Exception:
                    continue

        except ImportError:
            logger.debug("AKShare library not installed — returning empty fund list")
        except Exception:
            logger.exception("AKShare: fund list fetch failed")

        logger.info("AKShare: fetched %d funds", len(results))
        return results

    # -- NAV history --------------------------------------------------------

    async def fetch_nav(
        self, fund_code: str, start_date: date, end_date: date
    ) -> list[NavRaw]:
        """
        Fetch NAV history from AKShare.

        Uses ``akshare.fund_open_fund_info_em`` if available.
        """
        results: list[NavRaw] = []
        try:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.fund_open_fund_info_em(
                symbol=fund_code,
                indicator="单位净值走势",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                logger.warning("AKShare: NAV history empty for %s", fund_code)
                return results

            for _, row in df.iterrows():
                try:
                    nav_date = _safe_date(row.get("净值日期", row.get("日期", "")))
                    nav = _safe_decimal(row.get("单位净值", None))
                    if nav_date is None or nav is None:
                        continue
                    acc = _safe_decimal(row.get("累计净值", None))
                    dr = _safe_decimal(row.get("日增长率", None))
                    if dr is not None:
                        dr = dr / Decimal("100") if abs(dr) > Decimal("1") else dr

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
            logger.debug("AKShare library not installed — returning empty NAV list")
        except Exception:
            logger.exception("AKShare: NAV fetch failed for %s", fund_code)

        logger.info(
            "AKShare: fetched %d NAV records for %s (%s → %s)",
            len(results),
            fund_code,
            start_date,
            end_date,
        )
        return results

    # -- Fund detail --------------------------------------------------------

    async def fetch_fund_detail(self, fund_code: str) -> FundDetailRaw | None:
        """
        Fetch fund metadata from AKShare.

        Uses ``akshare.fund_individual_basic_info_xq`` or similar if available.
        """
        try:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.fund_individual_basic_info_xq(symbol=fund_code)
            if df is None or df.empty:
                logger.warning("AKShare: no detail info for %s", fund_code)
                return None

            row = df.iloc[0] if not df.empty else None
            if row is None:
                return None

            scale = _safe_decimal(row.get("基金规模", row.get("asset_scale", None)))
            fee_rate = _safe_decimal(row.get("管理费率", row.get("management_fee", None)))
            company = str(row.get("基金管理人", row.get("fund_company", ""))) or None
            manager_name = str(row.get("基金经理", row.get("manager_name", ""))) or None
            manager_start_date = _safe_date(row.get("manager_start_date", None))
            manager_tenure_return = _safe_decimal(row.get("manager_return", None))

            return FundDetailRaw(
                code=fund_code,
                scale=scale,
                fee_rate=fee_rate,
                company=company,
                manager_name=manager_name,
                manager_start_date=manager_start_date,
                manager_tenure_return=manager_tenure_return,
            )

        except ImportError:
            logger.debug("AKShare library not installed — returning empty detail")
        except Exception:
            logger.exception("AKShare: detail fetch failed for %s", fund_code)

        return None

    # -- Holdings -----------------------------------------------------------

    async def fetch_fund_holdings(self, fund_code: str) -> list[FundHoldingRaw]:
        """
        Fetch top-holdings from AKShare.

        Uses ``akshare.fund_portfolio_hold_detail_em`` if available.
        """
        results: list[FundHoldingRaw] = []
        try:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.fund_portfolio_hold_detail_em(symbol=fund_code)
            if df is None or df.empty:
                logger.warning("AKShare: no holdings for %s", fund_code)
                return results

            for _, row in df.iterrows():
                try:
                    stock_code = str(row.get("股票代码", "")).strip()
                    stock_name = str(row.get("股票名称", "")).strip()
                    ratio = _safe_decimal(row.get("占净值比例", row.get("ratio", None)))
                    report_date = _safe_date(row.get("报告期", row.get("report_date", ""))) or date.today()

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
            logger.debug("AKShare library not installed — returning empty holdings")
        except Exception:
            logger.exception("AKShare: holdings fetch failed for %s", fund_code)

        if not results:
            logger.warning("AKShare: no holdings parsed for %s", fund_code)
        else:
            logger.info("AKShare: fetched %d holdings for %s", len(results), fund_code)

        return results
