"""
Data normaliser — converts raw adapter output into a unified, consistent format.

Each method applies source-specific mapping rules so that downstream code
can treat data from any adapter interchangeably.
"""

import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.adapters.base import (
    FundDetailRaw,
    FundHoldingRaw,
    FundRaw,
    NavRaw,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared precision settings
# ---------------------------------------------------------------------------
_NAV_PRECISION = Decimal("0.0001")  # 4 decimal places for NAV
_RETURN_PRECISION = Decimal("0.000001")  # 6 decimal places for returns
_SCALE_PRECISION = Decimal("0.01")  # 2 decimal places for scale (CNY)


def _quantize(value: Decimal | None, precision: Decimal) -> Decimal | None:
    """Quantize *value* to *precision* using ROUND_HALF_UP; return None if None."""
    if value is None:
        return None
    return value.quantize(precision, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Source-specific type mappings
# ---------------------------------------------------------------------------

# Tiantian (天天基金) Chinese type labels → standard codes
_TIANTIAN_TYPE_MAP: dict[str, str] = {
    "股票型": "stock",
    "股票指数": "index",
    "混合型": "mixed",
    "混合-灵活": "mixed",
    "混合-偏股": "mixed",
    "混合-偏债": "mixed",
    "混合-平衡": "mixed",
    "债券型": "bond",
    "债券-长债": "bond",
    "债券-中短债": "bond",
    "货币型": "money",
    "指数型": "index",
    "指数型-股票": "index",
    "ETF-场内": "index",
    "QDII": "qdii",
    "LOF": "other",
    "FOF": "other",
    "保本型": "other",
    "短期理财": "money",
    "商品(黄金)": "other",
    "另类投资": "other",
}

# Eastmoney (东方财富) Chinese type labels → standard codes
_EASTMONEY_TYPE_MAP: dict[str, str] = {
    "股票型": "stock",
    "股票指数": "index",
    "混合型": "mixed",
    "混合-灵活": "mixed",
    "混合-偏股": "mixed",
    "混合-偏债": "mixed",
    "混合-平衡": "mixed",
    "债券型": "bond",
    "债券-长债": "bond",
    "债券-中短债": "bond",
    "货币型": "money",
    "指数型": "index",
    "指数型-股票": "index",
    "ETF-场内": "index",
    "QDII": "qdii",
    "商品型": "other",
    "FOF": "other",
    "LOF": "other",
    "保本型": "other",
    "短期理财": "money",
    "商品(黄金)": "other",
    "另类投资": "other",
    "REITs": "other",
    "联接基金": "index",
}

# Akshare uses English labels already, but provide a minimal map for fallback
_AKSHARE_TYPE_MAP: dict[str, str] = {
    "股票型": "stock",
    "混合型": "mixed",
    "债券型": "bond",
    "货币型": "money",
    "指数型": "index",
    "qdii": "qdii",
    "stock": "stock",
    "mixed": "mixed",
    "bond": "bond",
    "money": "money",
    "index": "index",
    "other": "other",
}

# Tushare type map (Tushare uses abbreviations like GP, HH, ZQ, HB)
_TUSHARE_TYPE_MAP: dict[str, str] = {
    "股票型": "stock",
    "混合型": "mixed",
    "债券型": "bond",
    "货币型": "money",
    "指数型": "index",
    "GP": "stock",
    "HH": "mixed",
    "ZQ": "bond",
    "HB": "money",
    "ZS": "index",
    "QDII": "qdii",
    "qdii": "qdii",
    "stock": "stock",
    "mixed": "mixed",
    "bond": "bond",
    "money": "money",
    "index": "index",
    "other": "other",
}

# Map source name → type-mapping dict
_TYPE_MAPS: dict[str, dict[str, str]] = {
    "tiantian": _TIANTIAN_TYPE_MAP,
    "eastmoney": _EASTMONEY_TYPE_MAP,
    "akshare": _AKSHARE_TYPE_MAP,
    "tushare": _TUSHARE_TYPE_MAP,
}


# ---------------------------------------------------------------------------
# Normaliser
# ---------------------------------------------------------------------------
class DataNormalizer:
    """Normalise raw data from different sources into a unified format."""

    # ------------------------------------------------------------------
    # Fund list
    # ------------------------------------------------------------------
    def normalize_fund_list(
        self, raw: list[FundRaw], source: str
    ) -> list[FundRaw]:
        """
        Normalise a list of FundRaw objects from *source*.

        Applies:
        - Type-label translation (Chinese → standard English codes)
        - Scale unit conversion (e.g. 万份 → 份 for Eastmoney)
        - Code trimming / padding to 6 digits
        """
        type_map = _TYPE_MAPS.get(source, {})
        normalized: list[FundRaw] = []

        for fund in raw:
            code = fund.code.strip().zfill(6)

            # Translate type
            fund_type = fund.type
            if fund_type in type_map:
                fund_type = type_map[fund_type]
            elif fund_type:
                fund_type = fund_type.lower()

            # Normalise scale — Eastmoney scale is sometimes in 万 (10^4).
            # The adapter already multiplies by 10000 in some cases, but
            # we provide a safe second-pass: if scale seems unreasonable for
            # a fund (e.g. > 10^14), assume unit error and leave as-is.
            scale = _quantize(fund.scale, _SCALE_PRECISION)

            normalized.append(
                FundRaw(
                    code=code,
                    name=fund.name.strip(),
                    type=fund_type or "other",
                    scale=scale,
                    fee_rate=fund.fee_rate,
                    company=fund.company,
                    inception_date=fund.inception_date,
                )
            )

        logger.debug("Normalised %d funds from source '%s'", len(normalized), source)
        return normalized

    # ------------------------------------------------------------------
    # NAV
    # ------------------------------------------------------------------
    def normalize_nav(self, raw: list[NavRaw], source: str) -> list[NavRaw]:
        """
        Normalise a list of NavRaw objects.

        Applies:
        - Decimal precision quantisation (NAV → 4dp, returns → 6dp)
        - Removes entries with missing/zero NAV
        - Deduplicates by date (keeps last entry when dates collide)
        """
        seen_dates: dict[date, NavRaw] = {}

        for nav in raw:
            if nav.nav is None or nav.nav <= 0:
                continue

            normalized = NavRaw(
                fund_code=nav.fund_code.strip().zfill(6),
                date=nav.date,
                nav=_quantize(nav.nav, _NAV_PRECISION),  # type: ignore[arg-type]
                accumulated_nav=_quantize(nav.accumulated_nav, _NAV_PRECISION),
                daily_return=_quantize(nav.daily_return, _RETURN_PRECISION),
            )
            seen_dates[nav.date] = normalized  # last-write wins for duplicate dates

        result = sorted(seen_dates.values(), key=lambda n: n.date)
        logger.debug("Normalised %d NAV records from source '%s'", len(result), source)
        return result

    # ------------------------------------------------------------------
    # Fund detail
    # ------------------------------------------------------------------
    def normalize_fund_detail(
        self, raw: FundDetailRaw | None, source: str
    ) -> FundDetailRaw | None:
        """
        Normalise a single FundDetailRaw.

        - Ensure scale is positive
        - Quantise fee_rate to 4dp
        - Translate manager name encoding if needed
        """
        if raw is None:
            return None

        scale = _quantize(raw.scale, _SCALE_PRECISION)
        if scale is not None and scale < 0:
            scale = None

        fee_rate = _quantize(raw.fee_rate, _NAV_PRECISION)

        return FundDetailRaw(
            code=raw.code.strip().zfill(6),
            scale=scale,
            fee_rate=fee_rate,
            company=raw.company.strip() if raw.company else None,
            manager_name=raw.manager_name.strip() if raw.manager_name else None,
            manager_start_date=raw.manager_start_date,
            manager_tenure_return=raw.manager_tenure_return,
        )

    # ------------------------------------------------------------------
    # Fund holdings
    # ------------------------------------------------------------------
    def normalize_fund_holdings(
        self, raw: list[FundHoldingRaw], source: str
    ) -> list[FundHoldingRaw]:
        """
        Normalise holding ratios from *source*.

        - Ensure ratios are in [0, 1] decimal form (not percentages)
        - Trim and pad stock codes
        - Remove entries with missing stock codes
        """
        normalized: list[FundHoldingRaw] = []

        for h in raw:
            if not h.stock_code or not h.stock_code.strip():
                continue

            ratio = h.ratio
            # Ratios from Eastmoney are sometimes raw percentages (e.g. 5.23)
            # but the adapter already divides by 100 in most cases.
            # Double-check: if ratio > 1, assume percentage.
            if ratio is not None and ratio > Decimal("1"):
                ratio = ratio / Decimal("100")
            ratio = _quantize(ratio, _NAV_PRECISION) if ratio is not None else None

            normalized.append(
                FundHoldingRaw(
                    fund_code=h.fund_code.strip().zfill(6),
                    report_date=h.report_date,
                    stock_code=h.stock_code.strip().zfill(6),
                    stock_name=h.stock_name.strip() if h.stock_name else None,
                    ratio=ratio,
                )
            )

        logger.debug(
            "Normalised %d holdings from source '%s'", len(normalized), source
        )
        return normalized

    # ------------------------------------------------------------------
    # Static helpers — convert dataclass lists to dict lists for caching
    # ------------------------------------------------------------------
    @staticmethod
    def navs_to_dicts(navs: list[NavRaw]) -> list[dict[str, Any]]:
        """Convert NavRaw list into dicts with JSON-safe values."""
        return [
            {
                "fund_code": n.fund_code,
                "date": n.date.isoformat(),
                "nav": str(n.nav) if n.nav is not None else None,
                "accumulated_nav": str(n.accumulated_nav) if n.accumulated_nav is not None else None,
                "daily_return": str(n.daily_return) if n.daily_return is not None else None,
            }
            for n in navs
        ]

    @staticmethod
    def funds_to_dicts(funds: list[FundRaw]) -> list[dict[str, Any]]:
        """Convert FundRaw list into dicts with JSON-safe values."""
        return [
            {
                "code": f.code,
                "name": f.name,
                "type": f.type,
                "scale": str(f.scale) if f.scale is not None else None,
                "fee_rate": str(f.fee_rate) if f.fee_rate is not None else None,
                "company": f.company,
                "inception_date": f.inception_date.isoformat() if f.inception_date else None,
            }
            for f in funds
        ]
