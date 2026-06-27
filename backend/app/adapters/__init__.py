"""
Adapter registry and factory for external data-source adapters.

Every adapter is registered in ADAPTER_REGISTRY by its ``source_name``.
Use ``get_adapter(name)`` to obtain a singleton instance.
"""

import logging

from app.adapters.akshare import AKShareAdapter
from app.adapters.base import BaseAdapter
from app.adapters.eastmoney import EastmoneyAdapter
from app.adapters.tiantian import TiantianAdapter
from app.adapters.tushare import TushareAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry — maps source name → adapter class
# ---------------------------------------------------------------------------
ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "tiantian": TiantianAdapter,
    "eastmoney": EastmoneyAdapter,
    "akshare": AKShareAdapter,
    "tushare": TushareAdapter,
}

# ---------------------------------------------------------------------------
# Singleton cache — holds one instance per adapter type
# ---------------------------------------------------------------------------
_instances: dict[str, BaseAdapter] = {}


def get_adapter(name: str) -> BaseAdapter:
    """
    Return a singleton adapter instance for the given source *name*.

    Raises ``ValueError`` if *name* is not registered in ``ADAPTER_REGISTRY``.
    """
    name = name.strip().lower()
    cls = ADAPTER_REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown adapter '{name}'. "
            f"Registered adapters: {list(ADAPTER_REGISTRY)}"
        )

    if name not in _instances:
        logger.info("Creating singleton adapter instance for '%s'", name)
        _instances[name] = cls()

    return _instances[name]


__all__ = [
    "ADAPTER_REGISTRY",
    "AKShareAdapter",
    "BaseAdapter",
    "EastmoneyAdapter",
    "TiantianAdapter",
    "TushareAdapter",
    "get_adapter",
]
