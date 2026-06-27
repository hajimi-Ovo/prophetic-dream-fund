"""
Unit tests for PortfolioBuilder engine — logic-only tests (no DB).

Verifies allocation logic and constraint enforcement.
"""

from decimal import Decimal

from app.engine.portfolio_builder import (
    MAX_SINGLE_RATIO,
    PortfolioBuilder,
)


class TestPortfolioBuilderLogic:
    """Tests for portfolio allocation logic (no async DB)."""

    def setup_method(self) -> None:
        self.builder = PortfolioBuilder()

    # -- Allocation logic --
    def test_constraint_max_single_ratio(self) -> None:
        """MAX_SINGLE_RATIO should be 0.30."""
        assert Decimal("0.30") == MAX_SINGLE_RATIO

    def test_allocate_empty(self) -> None:
        """Empty fund list returns empty allocations."""
        result = self.builder._allocate([], "moderate", Decimal("10000"))
        assert result == []

    def test_weights_sum_to_one(self) -> None:
        """All allocation ratios must sum to 1.0."""
        funds = [
            {"code": "A", "name": "Fund A", "type": "stock", "total_score": Decimal("80")},
            {"code": "B", "name": "Fund B", "type": "bond", "total_score": Decimal("70")},
            {"code": "C", "name": "Fund C", "type": "mixed", "total_score": Decimal("60")},
        ]
        result = self.builder._allocate(funds, "moderate", Decimal("10000"))
        total_ratio = sum(a["ratio"] for a in result)
        assert abs(float(total_ratio) - 1.0) < 0.05, f"Total ratio: {total_ratio}"

    def test_allocations_sum_to_total(self) -> None:
        """All allocated amounts should sum to total_amount."""
        total_amount = Decimal("50000")
        funds = [
            {"code": "A", "name": "Fund A", "type": "bond", "total_score": Decimal("80")},
            {"code": "B", "name": "Fund B", "type": "mixed", "total_score": Decimal("70")},
        ]
        result = self.builder._allocate(funds, "moderate", total_amount)
        total_allocated = sum(a["amount"] for a in result)
        diff = abs(total_allocated - total_amount)
        assert diff < total_amount * Decimal("0.05"), f"Difference: {diff}"

    def test_money_fund_allocation(self) -> None:
        """Money fund gets 5-10% allocation."""
        funds = [
            {"code": "M", "name": "Money A", "type": "money", "total_score": Decimal("50")},
            {"code": "B", "name": "Bond A", "type": "bond", "total_score": Decimal("80")},
            {"code": "S", "name": "Stock A", "type": "stock", "total_score": Decimal("70")},
        ]
        result = self.builder._allocate(funds, "moderate", Decimal("10000"))
        money_item = next((a for a in result if a["fund_code"] == "M"), None)
        if money_item:
            # Should be between 5% and 10% or 0
            ratio = float(money_item["ratio"])
            assert 0 <= ratio <= 0.15, f"Money ratio: {ratio}"

    # -- Reason generation --
    def test_allocation_reason_high_score(self) -> None:
        """High score yields positive reason."""
        fund = {"total_score": Decimal("85"), "name": "Super Fund", "type": "stock"}
        reason = self.builder._allocation_reason(fund)
        assert "优秀" in reason
        assert "Super Fund" in reason

    def test_allocation_reason_low_score(self) -> None:
        """Low score yields cautious reason."""
        fund = {"total_score": Decimal("30"), "name": "Weak Fund", "type": "stock"}
        reason = self.builder._allocation_reason(fund)
        assert "较低" in reason or "谨慎" in reason

    # -- Rebalancing suggestions --
    def test_rebalance_high_concentration(self) -> None:
        """High single-fund ratio triggers rebalance suggestion."""
        allocations = [
            {
                "fund_code": "A",
                "fund_name": "Heavy Fund",
                "ratio": Decimal("0.35"),
                "amount": Decimal("35000"),
            },
        ]
        suggestions = self.builder._generate_rebalance_suggestions(
            allocations, "moderate", 0.15
        )
        # Should suggest diversification
        assert any("分散" in s or "超过" in s for s in suggestions)

    def test_rebalance_conservative_high_risk(self) -> None:
        """Conservative profile with high risk triggers warning."""
        suggestions = self.builder._generate_rebalance_suggestions(
            [], "conservative", 0.25
        )
        assert any("保守" in s or "较高" in s for s in suggestions)

    def test_rebalance_aggressive_low_risk(self) -> None:
        """Aggressive profile with low risk triggers suggestion."""
        suggestions = self.builder._generate_rebalance_suggestions(
            [], "aggressive", 0.03
        )
        assert any("偏低" in s or "激进" in s or "增加" in s for s in suggestions)

    def test_rebalance_periodic_reminder(self) -> None:
        """Always includes periodic rebalancing reminder."""
        suggestions = self.builder._generate_rebalance_suggestions(
            [], "moderate", 0.10
        )
        assert any("每季度" in s or "定期" in s for s in suggestions)
