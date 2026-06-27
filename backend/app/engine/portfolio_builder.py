"""
Portfolio construction engine — builds optimized asset allocations.

Applies risk-based constraints, prevents concentration, and produces
a plan with ratios, amounts, expected return/risk, and rebalancing tips.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.fund_ranker import FundRanker
from app.engine.risk_scorer import RiskScorer
from app.models.fund import FundNav
from app.utils.finance import calc_volatility

logger = logging.getLogger(__name__)

# Maximum allocation to a single fund
MAX_SINGLE_RATIO = Decimal("0.30")

# Money fund allocation bounds
MONEY_MIN_RATIO = Decimal("0.05")
MONEY_MAX_RATIO = Decimal("0.10")

# Risk-based stock-fund caps
STOCK_CAPS: dict[str, Decimal] = {
    "conservative": Decimal("0.10"),
    "moderate": Decimal("0.30"),
    "aggressive": Decimal("0.60"),
}


class PortfolioBuilder:
    """
    Async portfolio optimizer.

    Builds a diversified allocation plan that respects risk constraints
    and produces a viable investment proposal.
    """

    def __init__(self) -> None:
        self.ranker = FundRanker()
        self.scorer = RiskScorer()

    async def build(
        self,
        risk_profile: dict[str, Any],
        total_amount: Decimal,
        db: AsyncSession,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """
        Build an optimized portfolio plan.

        *risk_profile*: {'risk_tolerance': 'moderate', ...}
        *total_amount*: total CNY to allocate
        *db*: async DB session
        *top_n*: number of candidate funds to consider

        Returns a dict with allocation plan details.
        """
        total_amount = abs(total_amount)
        risk_level = risk_profile.get("risk_tolerance", "moderate")

        # 1. Fetch candidate funds from FundRanker
        from sqlalchemy import select

        from app.models.fund import Fund

        result = await db.execute(select(Fund).limit(top_n * 3))
        all_funds = result.scalars().all()

        fund_dicts: list[dict[str, Any]] = [
            {
                "code": f.code,
                "name": f.name,
                "type": f.type,
                "scale": f.scale,
                "fee_rate": f.fee_rate,
                "company": f.company,
            }
            for f in all_funds
        ]

        # Rank funds
        ranked = await self.ranker.rank(fund_dicts, db)
        top_funds = ranked[:top_n]

        if not top_funds:
            return {
                "total_amount": total_amount,
                "allocations": [],
                "expected_return": 0.0,
                "expected_risk": 0.0,
                "max_drawdown": 0.0,
                "rebalance_suggestions": [],
            }

        # 2. Score by risk fit
        risk_scored = self.scorer.score(risk_profile, top_funds)

        # 3. Build allocations respecting constraints
        allocations = self._allocate(risk_scored, risk_level, total_amount)

        # 4. Estimate portfolio metrics
        expected_return, expected_risk, max_dd = await self._estimate_metrics(
            allocations, db
        )

        # 5. Generate rebalancing suggestions
        rebalance = self._generate_rebalance_suggestions(
            allocations, risk_level, expected_risk
        )

        return {
            "total_amount": total_amount,
            "allocations": allocations,
            "expected_return": expected_return,
            "expected_risk": expected_risk,
            "max_drawdown": max_dd,
            "rebalance_suggestions": rebalance,
        }

    # ------------------------------------------------------------------
    # Allocation logic
    # ------------------------------------------------------------------
    def _allocate(
        self,
        scored_funds: list[dict[str, Any]],
        risk_level: str,
        total_amount: Decimal,
    ) -> list[dict[str, Any]]:
        """
        Allocate capital across scored funds respecting constraints.

        - Each single fund <= MAX_SINGLE_RATIO (30%)
        - Stock-funds total <= risk-based cap
        - Money funds: 5-10%
        """
        if not scored_funds:
            return []

        # Group funds by type
        stock_funds: list[dict[str, Any]] = []
        money_funds: list[dict[str, Any]] = []
        other_funds: list[dict[str, Any]] = []

        stock_types = {"stock", "混合", "hybrid", "mixed", "index", "指数", "etf"}
        money_types = {"money", "货币"}

        for f in scored_funds:
            ft = f.get("type", "")
            if ft in money_types:
                money_funds.append(f)
            elif ft in stock_types:
                stock_funds.append(f)
            else:
                other_funds.append(f)

        # Combine: prioritize money, then other, then stock
        ordered = money_funds + other_funds + stock_funds

        # Determine stock cap
        stock_cap = STOCK_CAPS.get(risk_level, Decimal("0.30"))

        allocations: list[dict[str, Any]] = []
        remaining_ratio = Decimal("1.00")
        stock_allocated = Decimal("0")
        money_allocated = Decimal("0")

        n = len(ordered)
        for idx, fund in enumerate(ordered):
            ft = fund.get("type", "")
            is_stock = ft in stock_types
            is_money = ft in money_types

            # Base ratio: proportional to score
            score = Decimal(str(fund.get("total_score", 50)))
            total_score_sum = sum(
                Decimal(str(f.get("total_score", 50))) for f in ordered[idx:]
            )
            if total_score_sum == 0:
                ratio = remaining_ratio / Decimal(str(max(n - idx, 1)))
            else:
                ratio = min(
                    remaining_ratio * score / total_score_sum,
                    MAX_SINGLE_RATIO,
                )

            # Apply constraints
            if is_stock:
                max_stock_left = stock_cap - stock_allocated
                ratio = min(ratio, max_stock_left)
                stock_allocated += ratio

            if is_money:
                total_money = money_allocated + ratio
                if total_money > MONEY_MAX_RATIO:
                    ratio = max(Decimal("0"), MONEY_MAX_RATIO - money_allocated)
                money_allocated += ratio

            if ratio <= 0:
                continue

            # Ensure min money allocation
            is_last_money = is_money and idx == len(ordered) - 1
            if not is_last_money and is_money and money_allocated < MONEY_MIN_RATIO:
                ratio = max(ratio, MONEY_MIN_RATIO - max(Decimal("0"), money_allocated - ratio))
                money_allocated = max(money_allocated, MONEY_MIN_RATIO)

            amount = total_amount * ratio
            remaining_ratio -= ratio

            allocations.append({
                "fund_code": fund.get("code", ""),
                "fund_name": fund.get("name", ""),
                "fund_type": fund.get("type", ""),
                "ratio": ratio,
                "amount": amount,
                "reason": self._allocation_reason(fund),
            })

        # 6. Ensure weights sum to ~1.0 (distribute remainder to last allocation)
        if allocations:
            total_ratio = sum(a["ratio"] for a in allocations)
            if total_ratio < Decimal("0.99"):
                diff = Decimal("1.0") - total_ratio
                last = allocations[-1]
                last["ratio"] += diff
                last["amount"] = total_amount * last["ratio"]

        return allocations

    @staticmethod
    def _allocation_reason(fund: dict[str, Any]) -> str:
        """Generate a human-readable reason for allocation."""
        score = float(fund.get("total_score", 50))
        name = fund.get("name", "this fund")

        if score >= 80:
            return f"{name} 综合评分优秀 ({score:.0f}), 建议较高配置"
        elif score >= 60:
            return f"{name} 综合评分良好 ({score:.0f}), 建议适当配置"
        elif score >= 40:
            return f"{name} 综合评分一般 ({score:.0f}), 建议少量配置"
        else:
            return f"{name} 综合评分较低 ({score:.0f}), 建议谨慎配置"

    # ------------------------------------------------------------------
    # Metrics estimation
    # ------------------------------------------------------------------
    async def _estimate_metrics(
        self, allocations: list[dict[str, Any]], db: AsyncSession
    ) -> tuple[float, float, float]:
        """Estimate portfolio-level expected return, risk, and max drawdown."""
        if not allocations:
            return 0.0, 0.0, 0.0

        fund_returns: list[float] = []
        fund_vols: list[float] = []
        weights: list[float] = []

        for a in allocations:
            code = a.get("fund_code", "")
            w = float(a.get("ratio", 0))

            # Get NAV history for this fund
            from sqlalchemy import select

            q = (
                select(FundNav)
                .where(FundNav.fund_code == code)
                .order_by(FundNav.date.asc())
                .limit(260)
            )
            result = await db.execute(q)
            rows = result.scalars().all()

            nav_vals = [r.nav for r in rows if r.nav is not None]
            if len(nav_vals) < 2:
                continue

            daily_rets: list[Decimal] = []
            for i in range(1, len(nav_vals)):
                if nav_vals[i - 1] != 0:
                    r = (nav_vals[i] - nav_vals[i - 1]) / nav_vals[i - 1]
                    daily_rets.append(r)

            if not daily_rets:
                continue

            avg_daily = float(sum(daily_rets) / len(daily_rets))
            ann_ret = avg_daily * 252.0
            ann_vol = calc_volatility(daily_rets)

            fund_returns.append(ann_ret)
            fund_vols.append(ann_vol)
            weights.append(w)

        if not weights:
            return 0.0, 0.0, 0.0

        # Normalize weights
        w_sum = sum(weights)
        if w_sum == 0:
            return 0.0, 0.0, 0.0
        weights = [w / w_sum for w in weights]

        # Portfolio return = weighted average
        port_return = sum(weights[i] * fund_returns[i] for i in range(len(weights)))

        # Portfolio risk = sqrt(w^T * cov * w), simplified as weighted vol
        port_risk = sum(weights[i] * fund_vols[i] for i in range(len(weights)))

        # Estimated max drawdown ≈ 2 * volatility (rule of thumb)
        max_dd = min(1.0, port_risk * 2.0)

        return round(port_return, 4), round(port_risk, 4), round(max_dd, 4)

    # ------------------------------------------------------------------
    # Rebalancing suggestions
    # ------------------------------------------------------------------
    @staticmethod
    def _generate_rebalance_suggestions(
        allocations: list[dict[str, Any]],
        risk_level: str,
        expected_risk: float,
    ) -> list[str]:
        """Generate rebalancing and risk-awareness suggestions."""
        suggestions: list[str] = []

        # Check single-fund concentration
        for a in allocations:
            ratio = float(a.get("ratio", 0))
            if ratio > 0.25:
                suggestions.append(
                    f"{a.get('fund_name', '某基金')} 占比 {ratio:.0%}, "
                    f"超过25%单一持仓上限, 建议适当分散"
                )

        # Risk level advice
        if risk_level == "conservative" and expected_risk > 0.15:
            suggestions.append(
                f"预期波动率 {expected_risk:.2%} 较高, "
                f"与保守风险偏好不匹配, 建议降低权益类基金比例"
            )
        elif risk_level == "aggressive" and expected_risk < 0.08:
            suggestions.append(
                f"预期波动率 {expected_risk:.2%} 偏低, "
                f"可能无法满足激进型收益目标, 建议增加权益类配置"
            )

        suggestions.append("建议每季度审视持仓, 根据市场变化动态调整")

        return suggestions
