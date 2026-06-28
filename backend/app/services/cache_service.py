"""
In-memory TTL cache — drop-in replacement for Redis-backed cache.

Provides the same CacheService public API backed by a dict + asyncio.Lock.
"""

import asyncio
import json
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON encoder
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
# In-memory store
# ---------------------------------------------------------------------------
class _CacheEntry:
    """A single cache entry with value and optional expiry."""
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: int | None = None) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl if ttl else None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and time.monotonic() > self.expires_at


class CacheService:
    """
    Async in-memory cache with per-key TTL support.

    Thread-safe via asyncio.Lock. Drop-in replacement for the Redis-backed
    CacheService — same public method names and signatures.
    """

    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Latest NAV
    # ------------------------------------------------------------------
    async def set_latest_nav(
        self,
        fund_code: str,
        nav: Decimal,
        accumulated_nav: Decimal | None = None,
        daily_return: Decimal | None = None,
    ) -> None:
        key = f"fund:{fund_code}:nav:latest"
        mapping: dict[str, str] = {"nav": str(nav)}
        if accumulated_nav is not None:
            mapping["accumulated_nav"] = str(accumulated_nav)
        if daily_return is not None:
            mapping["daily_return"] = str(daily_return)
        async with self._lock:
            self._store[key] = _CacheEntry(mapping, ttl=300)

    async def get_latest_nav(self, fund_code: str) -> dict[str, str] | None:
        key = f"fund:{fund_code}:nav:latest"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
        return entry.value

    # ------------------------------------------------------------------
    # 30-day NAV
    # ------------------------------------------------------------------
    async def set_nav_30d(self, fund_code: str, nav_points: list[dict[str, Any]]) -> None:
        key = f"fund:{fund_code}:nav:30d"
        async with self._lock:
            self._store[key] = _CacheEntry(nav_points, ttl=3600)

    async def get_nav_30d(self, fund_code: str) -> list[dict[str, Any]]:
        key = f"fund:{fund_code}:nav:30d"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return []
            if entry.expired:
                del self._store[key]
                return []
        return entry.value

    # ------------------------------------------------------------------
    # Fund list
    # ------------------------------------------------------------------
    async def set_fund_list(self, funds: list[dict[str, Any]]) -> None:
        key = "fund:list:all"
        async with self._lock:
            self._store[key] = _CacheEntry(funds, ttl=600)

    async def get_fund_list(self) -> list[dict[str, Any]] | None:
        key = "fund:list:all"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
        return entry.value

    # ------------------------------------------------------------------
    # Hot top 20
    # ------------------------------------------------------------------
    async def set_hot_top20(self, funds: list[dict[str, Any]]) -> None:
        key = "fund:hot:top20"
        async with self._lock:
            self._store[key] = _CacheEntry(funds, ttl=600)

    async def get_hot_top20(self) -> list[dict[str, Any]] | None:
        key = "fund:hot:top20"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
        return entry.value

    # ------------------------------------------------------------------
    # Refresh time
    # ------------------------------------------------------------------
    async def set_refresh_time(self, timestamp: str) -> None:
        key = "market:refresh_time"
        async with self._lock:
            self._store[key] = _CacheEntry(timestamp, ttl=None)

    async def get_refresh_time(self) -> str | None:
        key = "market:refresh_time"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
        return entry.value


# ---------------------------------------------------------------------------
# Module-level singleton (replaces the old get_redis() dependency)
# ---------------------------------------------------------------------------
_cache: CacheService | None = None


def get_cache() -> CacheService:
    """Return the module-level singleton CacheService."""
    global _cache
    if _cache is None:
        _cache = CacheService()
    return _cache
