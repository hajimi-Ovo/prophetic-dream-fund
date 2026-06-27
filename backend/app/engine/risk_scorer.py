"""
Risk scoring engine — maps risk profiles to fund-type weights and
computes risk-match scores for individual funds.

This engine is stateless and does NOT require database access.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class RiskScorer:
    """Score funds by how well they match a given risk tolerance."""

    # Suggested allocations by risk level (ratios sum to 1.0)
    RISK_MAPPING: dict[str, dict[str, float]] = {
        "conservative": {
            "bond_funds": 0.45,
            "money_funds": 0.30,
            "mixed_funds": 0.15,
            "index_funds": 0.05,
            "stock_funds": 0.05,
        },
        "moderate": {
            "mixed_funds": 0.30,
            "stock_funds": 0.25,
            "bond_funds": 0.20,
            "index_funds": 0.15,
            "money_funds": 0.10,
        },
        "aggressive": {
            "stock_funds": 0.45,
            "mixed_funds": 0.25,
            "index_funds": 0.15,
            "bond_funds": 0.10,
            "money_funds": 0.05,
        },
    }

    # Map fund type strings to allocation keys
    FUND_TYPE_MAP: dict[str, str] = {
        "stock": "stock_funds",
        "混合": "mixed_funds",
        "mixed": "mixed_funds",
        "hybrid": "mixed_funds",
        "bond": "bond_funds",
        "债券": "bond_funds",
        "money": "money_funds",
        "货币": "money_funds",
        "index": "index_funds",
        "指数": "index_funds",
        "etf": "index_funds",
    }

    def score(
        self, profile: dict[str, Any], funds: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Compute risk-match score for each fund.

        *profile* must contain ``risk_tolerance`` key (one of conservative,
        moderate, aggressive).

        *funds* is a list of dicts each with at least ``type`` key.

        Returns a list of dicts each containing original fields plus:
          - risk_score (Decimal): 0-100 risk match score
          - risk_match (str): high / medium / low
        """
        risk_level = profile.get("risk_tolerance", "moderate")
        weights = self.RISK_MAPPING.get(risk_level, self.RISK_MAPPING["moderate"])

        scored: list[dict[str, Any]] = []
        for fund in funds:
            fund_type = fund.get("type", "")
            alloc_key = self.FUND_TYPE_MAP.get(fund_type, "mixed_funds")
            weight = weights.get(alloc_key, 0.20)

            # Score = weight * 100 (normalized 0-100)
            risk_score = Decimal(str(round(weight * 100, 2)))

            # Determine risk match level
            if weight >= 0.25:
                risk_match = "high"
            elif weight >= 0.10:
                risk_match = "medium"
            else:
                risk_match = "low"

            fund_copy = dict(fund)
            fund_copy["risk_score"] = risk_score
            fund_copy["risk_match"] = risk_match
            scored.append(fund_copy)

        return scored

    def get_suggested_allocation(self, risk_level: str) -> dict[str, Decimal]:
        """
        Return suggested asset-allocation percentages for *risk_level*.

        Returns a dict with keys: stock_funds, mixed_funds, bond_funds,
        money_funds, index_funds, each as a Decimal ratio.
        """
        mapping = self.RISK_MAPPING.get(risk_level, self.RISK_MAPPING["moderate"])
        return {
            k: Decimal(str(round(v, 4))) for k, v in mapping.items()
        }
