"""
Abstract base class and raw-data dataclasses for external data-source adapters.

All adapters must inherit from BaseAdapter and implement its five abstract
fetch methods.  The dataclasses represent the canonical "raw" shapes that
every source must produce before normalisation.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw-data dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FundRaw:
    """Raw fund data from a source before normalisation."""

    code: str
    name: str
    type: str  # stock / mixed / bond / money / index / qdii / other
    scale: Decimal | None = None
    fee_rate: Decimal | None = None
    company: str | None = None
    inception_date: date | None = None


@dataclass
class NavRaw:
    """Raw NAV snapshot from a single day."""

    fund_code: str
    date: date
    nav: Decimal
    accumulated_nav: Decimal | None = None
    daily_return: Decimal | None = None


@dataclass
class FundDetailRaw:
    """Raw fund meta-data (scale, manager, fees, …)."""

    code: str
    scale: Decimal | None = None
    fee_rate: Decimal | None = None
    company: str | None = None
    manager_name: str | None = None
    manager_start_date: date | None = None
    manager_tenure_return: Decimal | None = None


@dataclass
class FundHoldingRaw:
    """Raw top-holding disclosure for a fund."""

    fund_code: str
    report_date: date
    stock_code: str | None = None
    stock_name: str | None = None
    ratio: Decimal | None = None


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------

class BaseAdapter(ABC):
    """
    Abstract base for all data-source adapters.

    Each subclass provides a unified async interface for fetching:
    - fund list
    - NAV history
    - fund detail / metadata
    - top holdings

    A simple health-check is included that issues a HEAD request against
    the source's base URL (subclasses must define ``_base_url``).
    """

    # Shared httpx client (optional — created lazily; not for long-lived usage)
    _client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique short name for this data source (e.g. 'tiantian')."""
        ...

    @property
    @abstractmethod
    def _base_url(self) -> str:
        """Base URL used for the health-check HEAD request."""
        ...

    # ------------------------------------------------------------------
    # Abstract fetch methods
    # ------------------------------------------------------------------
    @abstractmethod
    async def fetch_fund_list(self) -> list[FundRaw]:
        """Return all available funds from this source."""
        ...

    @abstractmethod
    async def fetch_nav(
        self, fund_code: str, start_date: date, end_date: date
    ) -> list[NavRaw]:
        """Return NAV history for *fund_code* between *start_date* and *end_date*."""
        ...

    @abstractmethod
    async def fetch_fund_detail(self, fund_code: str) -> FundDetailRaw | None:
        """Return fund metadata (manager, scale, fees).  ``None`` if not found."""
        ...

    @abstractmethod
    async def fetch_fund_holdings(self, fund_code: str) -> list[FundHoldingRaw]:
        """Return the latest top-holdings disclosure for *fund_code*."""
        ...

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        """
        Perform a lightweight HTTP HEAD against the source's base URL.

        Returns ``True`` if the server responds with a 2xx/3xx status;
        ``False`` otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.head(self._base_url, follow_redirects=True)
                return resp.is_success or resp.is_redirect
        except Exception:
            logger.exception("Health check failed for %s", self.source_name)
            return False
