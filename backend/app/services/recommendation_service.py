"""
Recommendation service — orchestrates the full smart-recommendation pipeline.

Uses the five engines (RiskScorer, FundRanker, TimingAdvisor,
PortfolioBuilder, Backtester) to generate personalised recommendations.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import (
    Backtester,
    FundRanker,
    PortfolioBuilder,
    RiskScorer,
    TimingAdvisor,
)
from app.models.fund import Fund
from app.models.recommendation import RecommendationLog, RiskProfile

logger = logging.getLogger(__name__)


class RecommendationService:
    """Async service that orchestrates the recommendation pipeline."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.risk_scorer = RiskScorer()
        self.fund_ranker = FundRanker()
        self.timing_advisor = TimingAdvisor()
        self.portfolio_builder = PortfolioBuilder()
        self.backtester = Backtester()

    # ==================================================================
    # Risk Assessment
    # ==================================================================
    async def save_risk_assessment(
        self, request: dict[str, Any], user_id: int | None = None
    ) -> dict[str, Any]:
        """
        Save or update the risk profile for a user.

        Upserts on user_id: if a profile exists it is updated; otherwise
        a new profile is created.
        """
        risk_tolerance = request.get("risk_tolerance", "moderate")
        investment_horizon = request.get("investment_horizon", "medium")
        return_expectation = request.get("return_expectation", "balanced")

        # Find existing profile for this user
        if user_id is not None:
            existing_q = select(RiskProfile).where(RiskProfile.user_id == user_id)
            existing_result = await self.db.execute(existing_q)
            existing = existing_result.scalar_one_or_none()
        else:
            existing = None

        if existing:
            existing.risk_tolerance = risk_tolerance
            existing.investment_horizon = investment_horizon
            existing.return_expectation = return_expectation
            existing.updated_at = datetime.now(UTC)
            profile = existing
        else:
            profile = RiskProfile(
                risk_tolerance=risk_tolerance,
                investment_horizon=investment_horizon,
                return_expectation=return_expectation,
                user_id=user_id,
            )
            self.db.add(profile)

        await self.db.flush()

        # Get suggested allocation
        suggested = self.risk_scorer.get_suggested_allocation(risk_tolerance)

        return {
            "risk_level": risk_tolerance,
            "suggested_allocation": suggested,
            "user_id": profile.user_id,
            "updated_at": profile.updated_at,
        }

    async def get_risk_assessment(
        self, user_id: int | None = None
    ) -> dict[str, Any] | None:
        """
        Get the latest risk profile for *user_id*.

        Returns None if no profile exists.
        """
        if user_id is not None:
            q = select(RiskProfile).where(RiskProfile.user_id == user_id)
        else:
            q = select(RiskProfile).order_by(RiskProfile.updated_at.desc()).limit(1)

        result = await self.db.execute(q)
        profile = result.scalar_one_or_none()

        if profile is None:
            return None

        suggested = self.risk_scorer.get_suggested_allocation(
            profile.risk_tolerance
        )

        return {
            "risk_level": profile.risk_tolerance,
            "suggested_allocation": suggested,
            "user_id": profile.user_id,
            "updated_at": profile.updated_at,
        }

    # ==================================================================
    # Recommended Funds
    # ==================================================================
    async def get_recommended_funds(
        self,
        risk_profile: dict[str, Any],
        strategy: str = "hybrid",
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Generate ranked fund recommendations for a risk profile.

        Pipeline: fetch funds → FundRanker → RiskScorer → sort → log
        """
        # Fetch all available funds
        fund_q = select(Fund).limit(limit * 5)
        result = await self.db.execute(fund_q)
        funds = result.scalars().all()

        if not funds:
            return {"items": [], "strategy": strategy, "total": 0}

        fund_dicts: list[dict[str, Any]] = [
            {
                "code": f.code,
                "name": f.name,
                "type": f.type,
                "scale": f.scale,
                "fee_rate": f.fee_rate,
                "company": f.company,
            }
            for f in funds
        ]

        # 1. Rank by multi-factor model
        ranked = await self.fund_ranker.rank(fund_dicts, self.db)

        # 2. Score by risk fit
        risk_scored = self.risk_scorer.score(risk_profile, ranked)

        # 3. Sort by composite (60% factor + 40% risk)
        for f_item in risk_scored:
            factor_score = f_item.get("total_score", Decimal("50"))
            risk_score = f_item.get("risk_score", Decimal("50"))
            composite = (
                factor_score * Decimal("0.6") + risk_score * Decimal("0.4")
            )
            f_item["composite_score"] = composite

        risk_scored.sort(
            key=lambda f: float(f.get("composite_score", 0)), reverse=True
        )

        top_n = risk_scored[:limit]

        # 4. Build items with reasons
        items: list[dict[str, Any]] = []
        for idx, f_item in enumerate(top_n):
            reasons = self._generate_reasons(f_item)
            suggested_action = self._suggested_action(f_item)
            suggested_amount = self._suggested_amount(f_item)

            items.append({
                "id": idx + 1,
                "rank": idx + 1,
                "fund_code": f_item.get("code", ""),
                "fund_name": f_item.get("name", ""),
                "fund_type": f_item.get("type", ""),
                "score": f_item.get("composite_score", Decimal("0")),
                "expected_return": f_item.get("expected_return", 0.0),
                "risk_level": f_item.get("risk_match", "medium"),
                "reasons": reasons,
                "suggested_action": suggested_action,
                "suggested_amount": suggested_amount,
            })

            # 5. Log recommendation
            await self._log_recommendation(f_item, strategy)

        return {"items": items, "strategy": strategy, "total": len(items)}

    # ==================================================================
    # Timing Advice
    # ==================================================================
    async def get_timing_advice(self, fund_code: str) -> dict[str, Any]:
        """Get valuation-based timing advice for a single fund."""
        return await self.timing_advisor.evaluate(fund_code, self.db)

    # ==================================================================
    # Amount Advice
    # ==================================================================
    async def get_amount_advice(
        self, risk_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Suggest an appropriate investment amount based on risk profile.

        Returns fixed-tier suggestions (simplified).
        """
        risk_level = risk_profile.get("risk_tolerance", "moderate")
        horizon = risk_profile.get("investment_horizon", "medium")

        tiers: dict[str, dict[str, int]] = {
            "conservative": {"min": 1000, "max": 10000, "suggested": 5000},
            "moderate": {"min": 5000, "max": 50000, "suggested": 10000},
            "aggressive": {"min": 10000, "max": 200000, "suggested": 50000},
        }

        tier = tiers.get(risk_level, tiers["moderate"])

        # Adjust by horizon
        horizon_multiplier: dict[str, float] = {
            "short": 0.5,
            "medium": 1.0,
            "long": 2.0,
            "very_long": 3.0,
        }
        mult = horizon_multiplier.get(horizon, 1.0)

        return {
            "min_amount": Decimal(str(tier["min"])),
            "max_amount": Decimal(str(tier["max"])),
            "suggested_amount": Decimal(str(int(tier["suggested"] * mult))),
            "risk_level": risk_level,
            "horizon": horizon,
        }

    # ==================================================================
    # Portfolio Plan
    # ==================================================================
    async def get_portfolio_plan(
        self,
        risk_profile: dict[str, Any],
        total_amount: Decimal,
    ) -> dict[str, Any]:
        """Build an optimized portfolio plan."""
        return await self.portfolio_builder.build(
            risk_profile, total_amount, self.db
        )

    # ==================================================================
    # Backtest
    # ==================================================================
    async def get_backtest(
        self, strategy: str = "hybrid", period: str = "3y"
    ) -> dict[str, Any]:
        """Run a historical backtest for *strategy* over *period*."""
        return await self.backtester.run(strategy, period, self.db)

    # ==================================================================
    # Private helpers
    # ==================================================================
    @staticmethod
    def _generate_reasons(fund: dict[str, Any]) -> list[str]:
        """Generate human-readable reasons for a recommendation."""
        reasons: list[str] = []

        total = float(fund.get("composite_score", fund.get("total_score", 50)))
        if total >= 75:
            reasons.append(f"综合评分优秀 ({total:.1f}/100)")
        elif total >= 60:
            reasons.append(f"综合评分良好 ({total:.1f}/100)")
        else:
            reasons.append(f"综合评分中等 ({total:.1f}/100)")

        # Factor breakdowns
        factors = [
            ("valuation_score", "估值因子"),
            ("momentum_score", "动量因子"),
            ("quality_score", "质量因子"),
            ("manager_score", "经理因子"),
            ("scale_score", "规模因子"),
            ("fee_score", "费率因子"),
        ]
        for key, label in factors:
            score_val = float(fund.get(key, 50))
            if score_val >= 75:
                reasons.append(f"{label}表现优秀 ({score_val:.0f})")

        risk_match = fund.get("risk_match", "medium")
        if risk_match == "high":
            reasons.append("与您的风险偏好高度匹配")
        elif risk_match == "medium":
            reasons.append("与您的风险偏好适度匹配")

        return reasons

    @staticmethod
    def _suggested_action(fund: dict[str, Any]) -> str:
        """Suggest an action based on composite score."""
        score = float(fund.get("composite_score", fund.get("total_score", 50)))
        if score >= 80:
            return "buy"
        elif score >= 65:
            return "accumulate"
        elif score >= 50:
            return "hold"
        elif score >= 35:
            return "wait"
        else:
            return "sell"

    @staticmethod
    def _suggested_amount(fund: dict[str, Any]) -> Decimal | None:
        """Suggest investment amount based on score."""
        score = float(fund.get("composite_score", fund.get("total_score", 50)))
        if score >= 80:
            return Decimal("10000")
        elif score >= 65:
            return Decimal("5000")
        elif score >= 50:
            return Decimal("3000")
        elif score >= 35:
            return None
        else:
            return None

    async def _log_recommendation(
        self, fund: dict[str, Any], strategy: str
    ) -> None:
        """Persist a recommendation log entry."""
        try:
            log_entry = RecommendationLog(
                fund_code=fund.get("code", ""),
                score=fund.get("composite_score", fund.get("total_score")),
                strategy=strategy,
                reasons={
                    "risk_match": fund.get("risk_match", "medium"),
                    "total_score": str(fund.get("total_score", "0")),
                    "composite_score": str(fund.get("composite_score", "0")),
                },
            )
            self.db.add(log_entry)
            await self.db.flush()
        except Exception:
            logger.exception("Failed to log recommendation for %s", fund.get("code"))
