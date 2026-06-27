"""
Unit tests for RiskScorer engine — pure logic, no DB required.
"""

from decimal import Decimal

from app.engine.risk_scorer import RiskScorer


class TestRiskScorer:
    """Tests for the risk scoring engine."""

    def setup_method(self) -> None:
        self.scorer = RiskScorer()

    # -- Risk mappings --
    def test_conservative_mapping(self) -> None:
        """Conservative profile weights sum to 1.0."""
        mapping = self.scorer.RISK_MAPPING["conservative"]
        total = sum(mapping.values())
        assert abs(total - 1.0) < 0.001

    def test_moderate_mapping(self) -> None:
        """Moderate profile weights sum to 1.0."""
        mapping = self.scorer.RISK_MAPPING["moderate"]
        total = sum(mapping.values())
        assert abs(total - 1.0) < 0.001

    def test_aggressive_mapping(self) -> None:
        """Aggressive profile weights sum to 1.0."""
        mapping = self.scorer.RISK_MAPPING["aggressive"]
        total = sum(mapping.values())
        assert abs(total - 1.0) < 0.001

    # -- Score method --
    def test_score_stock_fund_conservative(self) -> None:
        """Stock fund with conservative risk gets low risk score."""
        profile = {"risk_tolerance": "conservative"}
        funds = [{"code": "000001", "name": "Test Stock", "type": "stock"}]
        result = self.scorer.score(profile, funds)
        assert len(result) == 1
        # stock_funds weight in conservative = 0.05 → risk_score = 5
        assert result[0]["risk_score"] == Decimal("5.00")
        assert result[0]["risk_match"] == "low"

    def test_score_stock_fund_aggressive(self) -> None:
        """Stock fund with aggressive risk gets high risk score."""
        profile = {"risk_tolerance": "aggressive"}
        funds = [{"code": "000001", "name": "Test Stock", "type": "stock"}]
        result = self.scorer.score(profile, funds)
        assert len(result) == 1
        # stock_funds weight in aggressive = 0.45 → risk_score = 45
        assert result[0]["risk_score"] == Decimal("45.00")
        assert result[0]["risk_match"] == "high"

    def test_score_bond_fund_conservative(self) -> None:
        """Bond fund with conservative risk gets high risk score."""
        profile = {"risk_tolerance": "conservative"}
        funds = [{"code": "000002", "name": "Test Bond", "type": "bond"}]
        result = self.scorer.score(profile, funds)
        assert result[0]["risk_score"] == Decimal("45.00")
        assert result[0]["risk_match"] == "high"

    def test_score_money_fund(self) -> None:
        """Money fund with moderate risk."""
        profile = {"risk_tolerance": "moderate"}
        funds = [{"code": "000003", "name": "Money Market", "type": "money"}]
        result = self.scorer.score(profile, funds)
        # money_funds weight in moderate = 0.10 → risk_score = 10
        assert result[0]["risk_score"] == Decimal("10.00")
        assert result[0]["risk_match"] == "medium"

    def test_score_custom_chinese_fund_type(self) -> None:
        """Chinese fund type strings map correctly."""
        profile = {"risk_tolerance": "aggressive"}
        funds = [
            {"code": "000001", "name": "混合基金A", "type": "混合"},
            {"code": "000002", "name": "债券基金B", "type": "债券"},
            {"code": "000003", "name": "指数基金C", "type": "指数"},
        ]
        result = self.scorer.score(profile, funds)
        assert len(result) == 3
        # 混合 → mixed_funds = 0.25 → 25
        assert result[0]["risk_score"] == Decimal("25.00")
        # 债券 → bond_funds = 0.10 → 10
        assert result[1]["risk_score"] == Decimal("10.00")
        # 指数 → index_funds = 0.15 → 15
        assert result[2]["risk_score"] == Decimal("15.00")

    def test_score_unknown_fund_type(self) -> None:
        """Unknown fund type defaults to mixed_funds."""
        profile = {"risk_tolerance": "conservative"}
        funds = [{"code": "000099", "name": "Unknown", "type": "unknown"}]
        result = self.scorer.score(profile, funds)
        # mixed_funds weight in conservative = 0.15 → 15
        assert result[0]["risk_score"] == Decimal("15.00")

    def test_score_unknown_risk_level(self) -> None:
        """Unknown risk level defaults to moderate."""
        profile = {"risk_tolerance": "fantasy"}
        funds = [{"code": "000001", "name": "Stock", "type": "stock"}]
        result = self.scorer.score(profile, funds)
        # moderate stock_funds = 0.25 → 25
        assert result[0]["risk_score"] == Decimal("25.00")
        assert result[0]["risk_match"] == "high"

    def test_score_empty_funds(self) -> None:
        """Empty fund list returns empty list."""
        result = self.scorer.score({"risk_tolerance": "moderate"}, [])
        assert result == []

    # -- get_suggested_allocation --
    def test_get_allocation_conservative(self) -> None:
        """Suggested allocation for conservative."""
        alloc = self.scorer.get_suggested_allocation("conservative")
        total = sum(alloc.values())
        assert abs(float(total) - 1.0) < 0.01
        assert alloc["bond_funds"] > alloc["stock_funds"]
        assert alloc["money_funds"] > Decimal("0.20")

    def test_get_allocation_aggressive(self) -> None:
        """Suggested allocation for aggressive."""
        alloc = self.scorer.get_suggested_allocation("aggressive")
        total = sum(alloc.values())
        assert abs(float(total) - 1.0) < 0.01
        assert alloc["stock_funds"] > alloc["bond_funds"]
        assert alloc["stock_funds"] > Decimal("0.30")

    def test_get_allocation_returns_decimals(self) -> None:
        """All returned values are Decimal."""
        alloc = self.scorer.get_suggested_allocation("moderate")
        for key, val in alloc.items():
            assert isinstance(val, Decimal), f"{key} is not Decimal"
