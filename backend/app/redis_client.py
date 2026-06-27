"""
Async Redis client for caching and pub/sub.

Provides a lifespan-managed global connection and a FastAPI
dependency for injecting Redis into route handlers.
"""

import logging

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level Redis connection (initialised at startup)
_redis: Redis | None = None


async def get_redis() -> Redis:
    """
    FastAPI dependency that returns the global Redis connection.

    The connection is created lazily on first use. If Redis is unavailable,
    operations will fail at call time (services should handle this gracefully).
    """
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def init_redis() -> None:
    """Create and verify the global Redis connection (called at startup)."""
    global _redis
    try:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await _redis.ping()
        logger.info("Redis connected successfully")
    except Exception:
        logger.warning("Redis connection failed — continuing without cache")
        _redis = None


async def close_redis() -> None:
    """Close the global Redis connection (called at shutdown)."""
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None
