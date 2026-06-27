"""
Common FastAPI dependencies.

Re-exports and convenience wrappers for the most frequently used
dependency-injection callables.
"""

from app.database import get_db
from app.redis_client import get_redis

__all__ = ["get_db", "get_redis"]
