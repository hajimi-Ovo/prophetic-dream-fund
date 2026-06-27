"""
Recommendation engine package.

Exports all five engines used by the smart-recommendation pipeline:
RiskScorer, FundRanker, TimingAdvisor, PortfolioBuilder, Backtester.
"""

from app.engine.backtester import Backtester
from app.engine.fund_ranker import FundRanker
from app.engine.portfolio_builder import PortfolioBuilder
from app.engine.risk_scorer import RiskScorer
from app.engine.timing_advisor import TimingAdvisor

__all__ = [
    "Backtester",
    "FundRanker",
    "PortfolioBuilder",
    "RiskScorer",
    "TimingAdvisor",
]
