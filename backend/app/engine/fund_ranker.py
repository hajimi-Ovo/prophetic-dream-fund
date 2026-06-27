"""
Multi-factor fund ranking engine.

Scores funds across 6 weighted factors (Valuation, Momentum, Quality,
Manager, Scale, Fee) and returns a ranked list.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import FundManager, FundNav
from app.utils.finance import calc_period_returns, calc_sharpe_ratio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Factor weights — must sum to 1.0
# ---------------------------------------------------------------------------
FACTOR_WEIGHTS: dict[str, float] = {
    "valuation": 0.25,
    "momentum": 0.25,
    "quality": 0.20,
    "manager": 0.15,
    "scale": 0.10,
    "fee": 0.05,
}


class FundRanker:
    """Async multi-factor fund scoring engine."""

    # Optimal fund scale range (in CNY hundred millions)
    _OPTIMAL_SCALE_MIN: Decimal = Decimal("5")    # 500M
    _OPTIMAL_SCALE_MAX: Decimal = Decimal("100")   # 10B

    async def rank(
        self, funds: list[dict[str, Any]], db: AsyncSession
    ) -> list[dict[str, Any]]:
        """
        Rank *funds* by a composite weighted score.

        For each fund, computes 6 factor scores, normalizes to 0-100, and
        computes a weighted total.  Returns the list sorted by total_score
        descending, each dict enriched with factor breakdowns.
        """
        if not funds:
            return []

        # Compute factor scores for each fund
        scored: list[dict[str, Any]] = []
        for fund in funds:
            code = fund.get("code", "")
            fund_type = fund.get("type", "")

            # Grab NAV history for this fund
            nav_points = await self._get_nav_points(db, code, limit=260)  # ~1 year
            nav_values = [Decimal(str(p["nav"])) for p in nav_points if p.get("nav")]
            daily_returns = self._calc_daily_returns(nav_values)

            # ----- factor: valuation (NAV percentile as proxy) -----
            valuation_score = self._calc_valuation_score(nav_values)

            # ----- factor: momentum -----
            momentum_score = await self._calc_momentum_score(db, code)

            # ----- factor: quality (Sharpe + stability) -----
            quality_score = self._calc_quality_score(daily_returns)

            # ----- factor: manager -----
            manager_score = await self._calc_manager_score(db, code)

            # ----- factor: scale -----
            scale_score = self._calc_scale_score(fund.get("scale"))

            # ----- factor: fee -----
            fee_score = self._calc_fee_score(fund.get("fee_rate"))

            # Weighted total
            total = Decimal("0")
            factor_details: dict[str, Decimal] = {}
            for name, weight in FACTOR_WEIGHTS.items():
                raw = locals().get(f"{name}_score", Decimal("50"))
                if not isinstance(raw, Decimal):
                    raw = Decimal(str(raw))
                factor_score = raw
                total += factor_score * Decimal(str(weight))
                factor_details[name] = factor_score

            fund_copy = dict(fund)
            fund_copy["total_score"] = total
            fund_copy["valuation_score"] = factor_details["valuation"]
            fund_copy["momentum_score"] = factor_details["momentum"]
            fund_copy["quality_score"] = factor_details["quality"]
            fund_copy["manager_score"] = factor_details["manager"]
            fund_copy["scale_score"] = factor_details["scale"]
            fund_copy["fee_score"] = factor_details["fee"]
            scored.append(fund_copy)

        # Sort by total_score descending
        scored.sort(key=lambda f: float(f["total_score"]), reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Factor calculators (each returns Decimal 0-100)
    # ------------------------------------------------------------------
    def _calc_valuation_score(self, nav_values: list[Decimal]) -> Decimal:
        """
        Valuation score based on current NAV percentile.
        Lower percentile = cheaper = higher score (contrarian).
        Returns 0-100.
        """
        if len(nav_values) < 10:
            return Decimal("50")

        current = nav_values[-1]
        minimum = min(nav_values)
        maximum = max(nav_values)

        if maximum == minimum:
            return Decimal("50")

        # Percentile of current in range (0 = at min, 100 = at max)
        percentile = float((current - minimum) / (maximum - minimum)) * 100.0

        # Inverse: lower percentile → higher score (buy low)
        score = max(0.0, min(100.0, 100.0 - percentile))
        return Decimal(str(round(score, 2)))

    async def _calc_momentum_score(
        self, db: AsyncSession, fund_code: str
    ) -> Decimal:
        """Momentum score from 1/3/6/12-month returns (0-100)."""
        nav_points = await self._get_nav_points(db, fund_code, limit=260)
        if len(nav_points) < 22:
            return Decimal("50")

        period_returns = calc_period_returns(nav_points)

        # Extract returns, default 0
        r1 = float(period_returns.get("monthly") or 0)
        r3 = float(period_returns.get("three_month") or 0)
        r6 = float(period_returns.get("six_month") or 0)
        r12 = float(period_returns.get("one_year") or 0)

        # Weight shorter periods less
        momentum = r1 * 0.1 + r3 * 0.2 + r6 * 0.3 + r12 * 0.4

        # Normalize to 0-100 (assume -20% to +50% range)
        normalized = max(0.0, min(100.0, (momentum + 0.20) / 0.70 * 100.0))
        return Decimal(str(round(normalized, 2)))

    def _calc_quality_score(self, daily_returns: list[Decimal]) -> Decimal:
        """Quality score from Sharpe ratio (0-100)."""
        if len(daily_returns) < 22:
            return Decimal("50")

        sharpe = calc_sharpe_ratio(daily_returns, risk_free_rate=0.03)

        # Map Sharpe to 0-100: Sharpe of 2+ = 100, 0 = 40, -1 = 0
        score = max(0.0, min(100.0, (sharpe + 1.0) / 3.0 * 100.0))
        return Decimal(str(round(score, 2)))

    async def _calc_manager_score(
        self, db: AsyncSession, fund_code: str
    ) -> Decimal:
        """Manager score from tenure return and experience (0-100)."""
        result = await db.execute(
            select(FundManager)
            .where(FundManager.fund_code == fund_code)
            .order_by(FundManager.start_date.desc())
            .limit(1)
        )
        manager = result.scalar_one_or_none()

        if manager is None:
            return Decimal("50")

        # Tenure return: map 0-200% return to 0-100
        tenure = float(manager.tenure_return or 0)
        tenure_score = max(0.0, min(100.0, tenure / 2.0 * 100.0))

        # Experience: years since start_date
        exp_score = 50.0
        if manager.start_date:
            years = (date.today() - manager.start_date).days / 365.25
            exp_score = max(0.0, min(100.0, years / 10.0 * 100.0))

        combined = tenure_score * 0.7 + exp_score * 0.3
        return Decimal(str(round(combined, 2)))

    def _calc_scale_score(self, scale: Any) -> Decimal:
        """
        Scale score: optimal size is mid-range (5-100 hundred million CNY).
        Very small or very large funds get penalized.
        """
        if scale is None:
            return Decimal("50")

        try:
            scale_dec = Decimal(str(scale))
        except (ValueError, TypeError, Exception):
            return Decimal("50")

        # Convert to hundred-millions
        scale_hm = scale_dec / Decimal("100000000")

        if scale_hm < self._OPTIMAL_SCALE_MIN:
            # Too small: 0 at 0, 80 at min (smooth transition into optimal range)
            score = max(0.0, min(100.0, float(scale_hm / self._OPTIMAL_SCALE_MIN) * 80.0))
        elif scale_hm > self._OPTIMAL_SCALE_MAX:
            # Too large: penalty increases
            excess = float(scale_hm - self._OPTIMAL_SCALE_MAX)
            score = max(0.0, 100.0 - excess * 2.0)
        else:
            # In optimal range: 80-100
            position = float((scale_hm - self._OPTIMAL_SCALE_MIN) /
                             (self._OPTIMAL_SCALE_MAX - self._OPTIMAL_SCALE_MIN))
            score = 80.0 + position * 20.0

        return Decimal(str(round(max(0.0, min(100.0, score)), 2)))

    def _calc_fee_score(self, fee_rate: Any) -> Decimal:
        """Fee score: lower fee → higher score (0-100)."""
        if fee_rate is None:
            return Decimal("50")

        try:
            fee = float(str(fee_rate))
        except (ValueError, TypeError):
            return Decimal("50")

        # Typical fee range: 0.1% to 2.0%
        # Score: 0% fee = 100, 2% fee = 0
        score = max(0.0, min(100.0, (0.02 - fee) / 0.02 * 100.0))
        return Decimal(str(round(score, 2)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_nav_points(
        self, db: AsyncSession, fund_code: str, limit: int = 260
    ) -> list[dict[str, Any]]:
        """Fetch ordered NAV points for a fund."""
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

    @staticmethod
    def _calc_daily_returns(nav_values: list[Decimal]) -> list[Decimal]:
        """Compute daily returns from ordered NAV values."""
        returns: list[Decimal] = []
        for i in range(1, len(nav_values)):
            if nav_values[i - 1] != 0:
                r = (nav_values[i] - nav_values[i - 1]) / nav_values[i - 1]
                returns.append(r)
        return returns
