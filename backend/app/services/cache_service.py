"""
Cache service — reads/writes Redis keys used by the API layer.

All Redis access flows through this service so that key schemas,
TTLs, and serialisation rules are enforced in one place.

Decimal values are serialised as strings to preserve precision.
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON encoder that handles Decimal and date
# ---------------------------------------------------------------------------
class _CacheEncoder(json.JSONEncoder):
    """Custom encoder: Decimal → str, date/datetime → isoformat."""

    def default(self, obj: object) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, date | datetime):
            return obj.isoformat()
        return super().default(obj)


def _serialize(value: Any) -> str:
    """JSON-dump *value* using the cache-aware encoder."""
    return json.dumps(value, cls=_CacheEncoder, ensure_ascii=False)


def _deserialize(text: str | bytes | None) -> Any:
    """JSON-load *text*; returns None on empty or parse failure."""
    if text is None:
        return None
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to decode cache JSON: %.100s...", text)
        return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class CacheService:
    """Async cache facade backed by Redis."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    # ------------------------------------------------------------------
    # Latest NAV (Hash)
    # ------------------------------------------------------------------
    async def set_latest_nav(
        self,
        fund_code: str,
        nav: Decimal,
        accumulated_nav: Decimal | None = None,
        daily_return: Decimal | None = None,
    ) -> None:
        """Set ``fund:{code}:nav:latest`` hash with TTL 300s."""
        key = f"fund:{fund_code}:nav:latest"
        mapping: dict[str, str] = {
            "nav": str(nav),
        }
        if accumulated_nav is not None:
            mapping["accumulated_nav"] = str(accumulated_nav)
        if daily_return is not None:
            mapping["daily_return"] = str(daily_return)

        try:
            await self.redis.hset(key, mapping=mapping)  # type: ignore[arg-type]
            await self.redis.expire(key, 300)
        except Exception:
            logger.exception("Failed to set latest NAV cache for %s", fund_code)

    async def get_latest_nav(self, fund_code: str) -> dict[str, str] | None:
        """Get ``fund:{code}:nav:latest`` hash.  Returns parsed dict or None."""
        key = f"fund:{fund_code}:nav:latest"
        try:
            data = await self.redis.hgetall(key)
            if data:
                return {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in data.items()}
            return None
        except Exception:
            logger.exception("Failed to get latest NAV cache for %s", fund_code)
            return None

    # ------------------------------------------------------------------
    # 30-day NAV (Sorted Set)
    # ------------------------------------------------------------------
    async def set_nav_30d(self, fund_code: str, nav_points: list[dict[str, Any]]) -> None:
        """
        Set ``fund:{code}:nav:30d`` ZSET with date-as-score, TTL 3600s.

        Each *nav_points* element should have keys: date (iso str), nav (str),
        accumulated_nav, daily_return.
        """
        key = f"fund:{fund_code}:nav:30d"
        try:
            pipe = self.redis.pipeline()
            for pt in nav_points:
                date_str = pt["date"]
                # Encode the full point as member, date iso string as score
                member = _serialize(pt)
                # Convert date to ordinal for numeric score
                try:
                    score = date.fromisoformat(date_str).toordinal()
                except (ValueError, TypeError):
                    score = 0
                pipe.zadd(key, {member: score})
            pipe.expire(key, 3600)
            await pipe.execute()
        except Exception:
            logger.exception("Failed to set NAV 30d cache for %s", fund_code)

    async def get_nav_30d(self, fund_code: str) -> list[dict[str, Any]]:
        """Get ``fund:{code}:nav:30d`` sorted by date ascending."""
        key = f"fund:{fund_code}:nav:30d"
        try:
            members = await self.redis.zrange(key, 0, -1)
            results: list[dict[str, Any]] = []
            for m in members:
                if isinstance(m, str | bytes):
                    parsed = _deserialize(m)
                    if parsed is not None:
                        results.append(parsed)
            return results
        except Exception:
            logger.exception("Failed to get NAV 30d cache for %s", fund_code)
            return []

    # ------------------------------------------------------------------
    # Fund list (String / JSON)
    # ------------------------------------------------------------------
    async def set_fund_list(self, funds: list[dict[str, Any]]) -> None:
        """Set ``fund:list:all`` as JSON string, TTL 600s."""
        key = "fund:list:all"
        try:
            await self.redis.setex(key, 600, _serialize(funds))
        except Exception:
            logger.exception("Failed to set fund list cache")

    async def get_fund_list(self) -> list[dict[str, Any]] | None:
        """Get ``fund:list:all``, parse JSON.  Returns None on miss."""
        key = "fund:list:all"
        try:
            raw = await self.redis.get(key)
            return _deserialize(raw) if raw else None
        except Exception:
            logger.exception("Failed to get fund list cache")
            return None

    # ------------------------------------------------------------------
    # Hot top 20 (String / JSON)
    # ------------------------------------------------------------------
    async def set_hot_top20(self, funds: list[dict[str, Any]]) -> None:
        """Set ``fund:hot:top20`` as JSON, TTL 600s."""
        key = "fund:hot:top20"
        try:
            await self.redis.setex(key, 600, _serialize(funds))
        except Exception:
            logger.exception("Failed to set hot top20 cache")

    async def get_hot_top20(self) -> list[dict[str, Any]] | None:
        """Get ``fund:hot:top20``."""
        key = "fund:hot:top20"
        try:
            raw = await self.redis.get(key)
            return _deserialize(raw) if raw else None
        except Exception:
            logger.exception("Failed to get hot top20 cache")
            return None

    # ------------------------------------------------------------------
    # Refresh time (String)
    # ------------------------------------------------------------------
    async def set_refresh_time(self, timestamp: str) -> None:
        """Set ``market:refresh_time`` string."""
        key = "market:refresh_time"
        try:
            await self.redis.set(key, timestamp)
        except Exception:
            logger.exception("Failed to set refresh time cache")

    async def get_refresh_time(self) -> str | None:
        """Get ``market:refresh_time``."""
        key = "market:refresh_time"
        try:
            raw = await self.redis.get(key)
            if raw is None:
                return None
            return raw.decode() if isinstance(raw, bytes) else str(raw)
        except Exception:
            logger.exception("Failed to get refresh time cache")
            return None
