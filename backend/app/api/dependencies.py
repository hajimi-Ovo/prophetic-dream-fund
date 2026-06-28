"""
Common FastAPI dependencies.

Re-exports the most frequently used dependency-injection callables.
"""

from app.database import get_db

__all__ = ["get_db"]
