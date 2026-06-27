"""
Models package — imports all ORM models so Alembic autogenerate can discover them.

Import order matters: Base must be imported first from database.
"""

from app.database import Base

# Import every model class so they are registered on Base.metadata
from app.models.data_source import DataSourceLog  # noqa: F401, E402
from app.models.fund import Fund, FundHolding, FundManager, FundNav  # noqa: F401, E402
from app.models.holding import FundTransaction, FundWatchlist, Holding  # noqa: F401, E402
from app.models.recommendation import RecommendationLog, RiskProfile  # noqa: F401, E402

__all__ = [
    "Base",
    "DataSourceLog",
    "Fund",
    "FundHolding",
    "FundManager",
    "FundNav",
    "FundTransaction",
    "FundWatchlist",
    "Holding",
    "RecommendationLog",
    "RiskProfile",
]
