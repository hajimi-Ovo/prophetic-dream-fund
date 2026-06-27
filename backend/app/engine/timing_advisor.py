"""
Timing advisor engine — valuation-based market timing signals.

Uses NAV percentile as a proxy for PE/PB percentile and moving-average
crossovers for trend detection.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundNav

logger = logging.getLogger(__name__)


class TimingAdvisor:
    """Valuation-based timing evaluation for a single fund."""

    # Signal thresholds based on valuation percentile
    SIGNAL_THRESHOLDS: list[tuple[float, float, str]] = [
        (0, 20, "buy"),
        (20, 40, "accumulate"),
        (40, 60, "hold"),
        (60, 80, "reduce"),
        (80, 100, "wait"),
    ]

    # Strong-buy signal when percentile < 10%
    STRONG_BUY_THRESHOLD: float = 10.0

    # Sell signal when percentile > 90%
    SELL_THRESHOLD: float = 90.0

    async def evaluate(
        self, fund_code: str, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Generate timing advice for *fund_code*.

        Returns a dict with:
          - fund_code, fund_name
          - valuation_percentile
          - signal
          - trend_signal
          - reasons
        """
        # Fetch fund name
        fund_result = await db.execute(select(Fund).where(Fund.code == fund_code))
        fund = fund_result.scalar_one_or_none()

        if fund is None:
            return {
                "fund_code": fund_code,
                "fund_name": "",
                "valuation_percentile": 50.0,
                "signal": "hold",
                "trend_signal": "neutral",
                "reasons": ["Fund not found; defaulting to hold."],
            }

        # Fetch 5-year NAV history for valuation percentile
        nav_pts = await self._get_nav_points(db, fund_code, limit=1260)  # ~5y
        if len(nav_pts) < 126:
            return {
                "fund_code": fund_code,
                "fund_name": fund.name,
                "valuation_percentile": 50.0,
                "signal": "hold",
                "trend_signal": "neutral",
                "reasons": ["Insufficient history for valuation analysis."],
            }

        nav_values = [Decimal(str(p["nav"])) for p in nav_pts if p.get("nav")]
        current_nav = nav_values[-1]
        min_nav = min(nav_values)
        max_nav = max(nav_values)

        # Valuation percentile (0 = cheap, 100 = expensive)
        if max_nav == min_nav:
            valuation_pct = 50.0
        else:
            valuation_pct = float(
                (current_nav - min_nav) / (max_nav - min_nav) * 100.0
            )

        # Determine signal
        signal = self._get_signal(valuation_pct)

        # Trend signal from moving averages
        trend_signal, trend_reasons = self._calc_trend_signal(nav_values)

        # Build reasons
        reasons: list[str] = []
        reasons.append(
            f"当前估值分位数: {valuation_pct:.1f}% "
            f"(近5年区间 [{float(min_nav):.4f}, {float(max_nav):.4f}])"
        )
        reasons.extend(trend_reasons)

        signal_map: dict[str, str] = {
            "buy": f"估值处于历史低位 ({valuation_pct:.1f}%), 建议买入",
            "accumulate": f"估值偏低 ({valuation_pct:.1f}%), 可逐步加仓",
            "hold": f"估值处于合理区间 ({valuation_pct:.1f}%), 建议持有",
            "reduce": f"估值偏高 ({valuation_pct:.1f}%), 建议减仓",
            "wait": f"估值处于历史高位 ({valuation_pct:.1f}%), 建议观望",
        }
        reasons.append(signal_map.get(signal, signal_map["hold"]))

        return {
            "fund_code": fund_code,
            "fund_name": fund.name,
            "valuation_percentile": round(valuation_pct, 2),
            "signal": signal,
            "trend_signal": trend_signal,
            "reasons": reasons,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _get_signal(self, percentile: float) -> str:
        """Map valuation percentile to a timing signal."""
        if percentile < self.STRONG_BUY_THRESHOLD:
            return "strong_buy"
        if percentile > self.SELL_THRESHOLD:
            return "sell"
        for lo, hi, sig in self.SIGNAL_THRESHOLDS:
            if lo <= percentile < hi:
                return sig
        return "hold"

    @staticmethod
    def _calc_ma(values: list[Decimal], window: int) -> list[float]:
        """Simple moving average over *window* periods."""
        floats = [float(v) for v in values]
        result: list[float] = []
        for i in range(len(floats)):
            if i + 1 < window:
                result.append(sum(floats[: i + 1]) / (i + 1))
            else:
                result.append(sum(floats[i - window + 1 : i + 1]) / window)
        return result

    def _calc_trend_signal(
        self, nav_values: list[Decimal]
    ) -> tuple[str, list[str]]:
        """Detect golden cross / dead cross from MA20 and MA60."""
        if len(nav_values) < 60:
            return "neutral", []

        ma20 = self._calc_ma(nav_values, 20)
        ma60 = self._calc_ma(nav_values, 60)

        reasons: list[str] = []

        # Check for crossover in the last 5 data points
        for i in range(max(0, len(nav_values) - 5), len(nav_values) - 1):
            if ma20[i] <= ma60[i] and ma20[i + 1] > ma60[i + 1]:
                reasons.append(
                    f"MA20 上穿 MA60 (黄金交叉), "
                    f"MA20={ma20[i + 1]:.4f}, MA60={ma60[i + 1]:.4f}"
                )
                return "golden_cross", reasons
            if ma20[i] >= ma60[i] and ma20[i + 1] < ma60[i + 1]:
                reasons.append(
                    f"MA20 下穿 MA60 (死亡交叉), "
                    f"MA20={ma20[i + 1]:.4f}, MA60={ma60[i + 1]:.4f}"
                )
                return "dead_cross", reasons

        # No recent crossover — use current relative position
        if ma20[-1] > ma60[-1]:
            reasons.append(
                f"MA20({ma20[-1]:.4f}) > MA60({ma60[-1]:.4f}), 短期趋势向上"
            )
            return "neutral", reasons
        else:
            reasons.append(
                f"MA20({ma20[-1]:.4f}) < MA60({ma60[-1]:.4f}), 短期趋势向下"
            )
            return "neutral", reasons

    async def _get_nav_points(
        self, db: AsyncSession, fund_code: str, limit: int = 1260
    ) -> list[dict[str, Any]]:
        """Fetch NAV points ordered by date ascending."""
        q = (
            select(FundNav)
            .where(FundNav.fund_code == fund_code)
            .order_by(FundNav.date.asc())
            .limit(limit)
        )
        result = await db.execute(q)
        rows = result.scalars().all()
        return [
            {"date": r.date, "nav": r.nav, "accumulated_nav": r.accumulated_nav}
            for r in rows
        ]
