"""
Cross-validator — compares data from multiple sources and generates
alerts when discrepancies exceed configured thresholds.

Used to detect stale / incorrect data and to decide which source to
trust per field (merge-strategy).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from decimal import Decimal

from app.adapters.base import FundRaw, NavRaw

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data class for validation alerts
# ---------------------------------------------------------------------------


@dataclass
class ValidationAlert:
    """Record of a discrepancy found between two data sources."""

    source_a: str
    source_b: str
    field_name: str
    fund_code: str
    value_a: Decimal | None = None
    value_b: Decimal | None = None
    difference: Decimal | None = None
    timestamp: datetime = dc_field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Cross Validator
# ---------------------------------------------------------------------------


class CrossValidator:
    """
    Compare data fetched from two different adapters and produce
    ``ValidationAlert`` instances when values diverge too far.
    """

    # Thresholds
    NAV_DIFF_THRESHOLD: Decimal = Decimal("0.0001")  # 0.01% in absolute terms
    SCALE_DIFF_RATIO: Decimal = Decimal("0.05")  # 5% relative difference for scale

    # ------------------------------------------------------------------
    # NAV validation
    # ------------------------------------------------------------------
    def validate_nav(
        self,
        navs_a: Sequence[NavRaw],
        navs_b: Sequence[NavRaw],
        source_a: str,
        source_b: str,
    ) -> list[ValidationAlert]:
        """
        Compare NAV values between two sources by matching on (fund_code, date).

        Returns alerts for any NAV where the absolute difference exceeds
        ``NAV_DIFF_THRESHOLD``, or where one source is missing a value the
        other has.
        """
        alerts: list[ValidationAlert] = []

        # Index navs_b by (fund_code, date) for O(1) lookup
        index_b: dict[tuple[str, str], NavRaw] = {}
        for n in navs_b:
            key = (n.fund_code, n.date.isoformat())
            index_b[key] = n

        for na in navs_a:
            key = (na.fund_code, na.date.isoformat())
            nb = index_b.get(key)

            if nb is None:
                # Exists in A but not B — flag if B has other records for
                # this fund code (suggesting a gap rather than a different scope).
                if any(n.fund_code == na.fund_code for n in navs_b):
                    alerts.append(
                        ValidationAlert(
                            source_a=source_a,
                            source_b=source_b,
                            field_name="nav",
                            fund_code=na.fund_code,
                            value_a=na.nav,
                            value_b=None,
                            difference=None,
                        )
                    )
                continue

            if na.nav is None or nb.nav is None:
                continue

            diff = abs(na.nav - nb.nav)
            if diff > self.NAV_DIFF_THRESHOLD:
                alerts.append(
                    ValidationAlert(
                        source_a=source_a,
                        source_b=source_b,
                        field_name="nav",
                        fund_code=na.fund_code,
                        value_a=na.nav,
                        value_b=nb.nav,
                        difference=diff,
                    )
                )

        logger.info(
            "NAV validation %s vs %s: %d alerts from %d / %d records",
            source_a,
            source_b,
            len(alerts),
            len(navs_a),
            len(navs_b),
        )
        return alerts

    # ------------------------------------------------------------------
    # Fund basic-info validation
    # ------------------------------------------------------------------
    def validate_fund_info(
        self,
        funds_a: Sequence[FundRaw],
        funds_b: Sequence[FundRaw],
        source_a: str,
        source_b: str,
    ) -> list[ValidationAlert]:
        """
        Compare fund basic info (name, type, scale) between two sources.

        Generates alerts for:
        - Name mismatch (warn if significantly different)
        - Type mismatch (e.g. one says 'stock', other says 'bond')
        - Scale mismatch (relative difference > SCALE_DIFF_RATIO)
        """
        alerts: list[ValidationAlert] = []

        # Index by fund code
        index_b: dict[str, FundRaw] = {f.code: f for f in funds_b}

        for fa in funds_a:
            fb = index_b.get(fa.code)
            if fb is None:
                continue  # fund only exists in A; no conflict to flag

            # --- Type ---
            if fa.type and fb.type and fa.type.lower() != fb.type.lower():
                alerts.append(
                    ValidationAlert(
                        source_a=source_a,
                        source_b=source_b,
                        field_name="type",
                        fund_code=fa.code,
                    )
                )

            # --- Name ---
            if fa.name.strip() != fb.name.strip():
                alerts.append(
                    ValidationAlert(
                        source_a=source_a,
                        source_b=source_b,
                        field_name="name",
                        fund_code=fa.code,
                    )
                )

            # --- Scale ---
            if fa.scale is not None and fb.scale is not None and fb.scale != 0:
                diff_ratio = abs(fa.scale - fb.scale) / abs(fb.scale)
                if diff_ratio > self.SCALE_DIFF_RATIO:
                    alerts.append(
                        ValidationAlert(
                            source_a=source_a,
                            source_b=source_b,
                            field_name="scale",
                            fund_code=fa.code,
                            value_a=fa.scale,
                            value_b=fb.scale,
                            difference=abs(fa.scale - fb.scale),
                        )
                    )

        logger.info(
            "Fund-info validation %s vs %s: %d alerts from %d / %d funds",
            source_a,
            source_b,
            len(alerts),
            len(funds_a),
            len(funds_b),
        )
        return alerts

    # ------------------------------------------------------------------
    # Merge strategy
    # ------------------------------------------------------------------
    def merge_strategy(
        self,
        data_a: object | None,
        data_b: object | None,
        data_c: object | None = None,
    ) -> dict[str, str | None]:
        """
        Return a dict mapping field names to the preferred source.

        Supports up to three sources (tiantian, eastmoney, akshare/tushare).

        Strategy priority:
        - For NAV: prefer Tiantian; fall back to Eastmoney; then akshare.
        - For fund meta-data (name, scale): use Eastmoney first.
        - For holdings: use whichever source has data.

        Callers should use the returned mapping like::

            strategy = validator.merge_strategy(nav_a, nav_b, nav_c)
            preferred = strategy.get("nav", "eastmoney")
        """
        strategy: dict[str, str | None] = {
            "nav": "tiantian",
            "name": "eastmoney",
            "type": "eastmoney",
            "scale": "eastmoney",
            "fee_rate": "eastmoney",
            "company": "eastmoney",
            "inception_date": "eastmoney",
            "manager_name": "tiantian",
            "manager_start_date": "tiantian",
            "manager_tenure_return": "tiantian",
            "holdings": "eastmoney",
        }

        # If only one source has data, prefer it
        has_a = data_a is not None
        has_b = data_b is not None
        has_c = data_c is not None

        if has_a and not has_b and not has_c:
            return dict.fromkeys(strategy, "tiantian")
        if has_b and not has_a and not has_c:
            return dict.fromkeys(strategy, "eastmoney")
        if has_c and not has_a and not has_b:
            return dict.fromkeys(strategy, "akshare")

        return strategy
