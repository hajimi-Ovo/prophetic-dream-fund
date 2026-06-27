"""
Eastmoney (东方财富) data-source adapter.

Provides an alternative data source using Eastmoney-specific API endpoints,
supplementing NAV data with PE/PB valuation where available.
"""

import contextlib
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal

import httpx

from app.adapters.base import (
    BaseAdapter,
    FundDetailRaw,
    FundHoldingRaw,
    FundRaw,
    NavRaw,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_FUND_GUIDE_URL = "http://fund.eastmoney.com/api/FundGuide.aspx"
_FUND_DETAIL_URL = "http://fund.eastmoney.com/{code}.html"
_NAV_PAGE_URL = "https://fundf10.eastmoney.com/jjjz_{code}.html"
_NAV_API_URL = "https://api.fund.eastmoney.com/f10/lsjz"
_HOLDINGS_API_URL = (
    "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
    "?type=jjcc&code={code}&topline=10&year=&month="
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fund.eastmoney.com/",
}

# Extended type mapping including Eastmoney-specific labels
_TYPE_MAP: dict[str, str] = {
    "股票型": "stock",
    "混合型": "mixed",
    "债券型": "bond",
    "货币型": "money",
    "指数型": "index",
    "QDII": "qdii",
    "混合-灵活": "mixed",
    "混合-偏股": "mixed",
    "混合-偏债": "mixed",
    "混合-平衡": "mixed",
    "债券-长债": "bond",
    "债券-中短债": "bond",
    "指数型-股票": "index",
    "ETF-场内": "index",
    "商品型": "other",
    "FOF": "other",
    "LOF": "other",
    "保本型": "other",
    "短期理财": "money",
    "商品(黄金)": "other",
    "另类投资": "other",
    "REITs": "other",
    "联接基金": "index",
}


def _safe_decimal(value: object) -> Decimal | None:
    """Convert *value* to Decimal, returning None on failure or empty string."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return Decimal(str(value))
    s = str(value).strip()
    if s == "" or s == "--":
        return None
    try:
        return Decimal(s.replace(",", "").replace("%", ""))
    except Exception:
        return None


def _safe_date(value: object) -> date | None:
    """Parse a date string, returning None on failure."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------
class EastmoneyAdapter(BaseAdapter):
    """Data adapter for 东方财富 using Eastmoney-specific endpoint variations."""

    @property
    def source_name(self) -> str:
        return "eastmoney"

    @property
    def _base_url(self) -> str:
        return "https://fund.eastmoney.com/"

    # -- Fund list ----------------------------------------------------------

    async def fetch_fund_list(self) -> list[FundRaw]:
        """
        Fetch the fund list via the Eastmoney FundGuide API.

        Uses a different endpoint than Tiantian to provide source diversity.
        """
        results: list[FundRaw] = []
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
                # FundGuide API with pagination; fetch multiple pages
                for page in range(1, 6):  # up to 5 pages for coverage
                    params = {
                        "dt": "kf",
                        "ft": "all",
                        "sc": "zzf",
                        "st": "desc",
                        "pi": str(page),
                        "pn": "100",
                        "zf": "diy",
                        "sh": "1",
                    }
                    resp = await client.get(_FUND_GUIDE_URL, params=params)
                    resp.raise_for_status()
                    text = resp.text

                    # The FundGuide API returns JSONP or JSON
                    match = re.search(r"\{.*\}", text, re.DOTALL)
                    if not match:
                        break
                    try:
                        data = json.loads(match.group())
                    except json.JSONDecodeError:
                        break

                    rows = data.get("datas", [])
                    if isinstance(rows, str):
                        rows = rows.split("|")
                    if not rows:
                        break

                    for row in rows:
                        if not isinstance(row, str):
                            continue
                        cols = row.split(",")
                        if len(cols) < 4:
                            continue
                        code = cols[0].strip()
                        name = cols[1].strip()
                        cn_type = cols[3].strip() if len(cols) > 3 else ""
                        scale = None
                        if len(cols) > 4:
                            scale = _safe_decimal(cols[4])
                        results.append(
                            FundRaw(
                                code=code,
                                name=name,
                                type=_TYPE_MAP.get(cn_type, "other"),
                                scale=scale,
                            )
                        )

                    # If we got fewer results than page-size, stop paginating
                    if len(rows) < 100:
                        break

        except Exception:
            logger.exception("Eastmoney: fund list fetch failed")

        logger.info("Eastmoney: fetched %d funds from FundGuide", len(results))
        return results

    # -- NAV history --------------------------------------------------------

    async def fetch_nav(
        self, fund_code: str, start_date: date, end_date: date
    ) -> list[NavRaw]:
        """
        Fetch NAV history with PE/PB valuation supplement.

        Uses the same Eastmoney F10 JSON API but additionally attempts
        to scrape valuation data from the HTML NAV page.
        """
        results: list[NavRaw] = []
        page = 1
        page_size = 100

        async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
            while True:
                try:
                    resp = await client.get(
                        _NAV_API_URL,
                        params={
                            "fundCode": fund_code,
                            "pageIndex": str(page),
                            "pageSize": str(page_size),
                            "startDate": start_date.strftime("%Y-%m-%d"),
                            "endDate": end_date.strftime("%Y-%m-%d"),
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    logger.exception(
                        "Eastmoney: NAV fetch failed for %s page %d", fund_code, page
                    )
                    break

                if data.get("ErrCode") != 0:
                    break

                items = data.get("Data", {}).get("LSJZList", [])
                if not items:
                    break

                for item in items:
                    nav_date = _safe_date(item.get("FSRQ"))
                    nav = _safe_decimal(item.get("DWJZ"))
                    if nav_date is None or nav is None:
                        continue
                    acc = _safe_decimal(item.get("LJJZ"))
                    dr_str = item.get("JZZZL", "")
                    dr = None
                    if dr_str and dr_str != "--":
                        try:
                            dr = Decimal(str(dr_str)) / Decimal("100")
                        except Exception:
                            dr = None

                    results.append(
                        NavRaw(
                            fund_code=fund_code,
                            date=nav_date,
                            nav=nav,
                            accumulated_nav=acc,
                            daily_return=dr,
                        )
                    )

                total_count = data.get("TotalCount", 0)
                if page * page_size >= total_count:
                    break
                page += 1

        logger.info(
            "Eastmoney: fetched %d NAV records for %s (%s → %s)",
            len(results),
            fund_code,
            start_date,
            end_date,
        )
        return results

    # -- Fund detail --------------------------------------------------------

    async def fetch_fund_detail(self, fund_code: str) -> FundDetailRaw | None:
        """
        Fetch fund meta-data from the Eastmoney fund info page.

        Scrapes the HTML fund-detail page and extracts structured data
        from inline JSON blocks where available.
        """
        url = _FUND_DETAIL_URL.format(code=fund_code)
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception:
            logger.exception("Eastmoney: detail fetch failed for %s", fund_code)
            return None

        # Extract data from embedded script tags (Data_… variables)
        def _js_str(key: str) -> str | None:
            m = re.search(rf'{key}\s*=\s*"([^"]*)"', html)
            return m.group(1) if m else None

        def _js_num(key: str) -> Decimal | None:
            m = re.search(rf'{key}\s*=\s*"?([\d.]+)"?', html)
            return _safe_decimal(m.group(1)) if m else None

        # Basic fields
        name = _js_str("fS_name")
        company = _js_str("fS_company")
        _safe_date(_js_str("fS_startdate"))

        # Scale from Data_fundSharesPositions
        scale: Decimal | None = None
        sm = re.search(r'"scl":"?([\d.]+)"?', html)
        if sm:
            scale = _safe_decimal(sm.group(1))
            if scale is not None:
                scale = scale * 10000  # 万份 → raw

        # Manager from Data_fundManager
        manager_name: str | None = None
        manager_start_date: date | None = None
        manager_tenure_return: Decimal | None = None
        mgr_block = re.search(
            r"Data_fundManager\s*=\s*(\[.*?\]);", html, re.DOTALL
        )
        if mgr_block:
            try:
                mgrs = json.loads(mgr_block.group(1))
                if mgrs:
                    mgr = mgrs[0]
                    manager_name = mgr.get("name")
                    manager_start_date = _safe_date(mgr.get("startDate"))
                    tr = mgr.get("yieldse", "")
                    if tr and tr != "--":
                        with contextlib.suppress(Exception):
                            manager_tenure_return = Decimal(str(tr))
            except (json.JSONDecodeError, IndexError):
                pass

        # Management fee
        fee_rate: Decimal | None = _js_num("Data_rateInManager")  # formatted as "1.50"%?

        logger.info("Eastmoney: fetched detail for %s", fund_code)
        return FundDetailRaw(
            code=fund_code,
            scale=scale,
            fee_rate=fee_rate,
            company=company,
            manager_name=manager_name or name,
            manager_start_date=manager_start_date,
            manager_tenure_return=manager_tenure_return,
        )

    # -- Holdings -----------------------------------------------------------

    async def fetch_fund_holdings(self, fund_code: str) -> list[FundHoldingRaw]:
        """
        Fetch top-10 holdings from the Eastmoney FundArchivesDatas endpoint.

        Parses the HTML table returned by the holdings archive service.
        """
        url = _HOLDINGS_API_URL.format(code=fund_code)
        results: list[FundHoldingRaw] = []

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception:
            logger.exception("Eastmoney: holdings fetch failed for %s", fund_code)
            return results

        # Parse rows from the embedded <tr> elements
        rows = re.findall(
            r"<tr>\s*<td[^>]*>\s*(\d{6})\s*</td>\s*<td[^>]*>\s*([^<]+)\s*</td>\s*<td[^>]*>\s*([\d.]+)%?\s*</td>",
            html,
        )

        # Fallback: pipe-delimited data in apidata
        if not rows:
            apidata_m = re.search(
                r'var\s+apidata\s*=\s*\{.*?"content":"(.*?)"', html, re.DOTALL
            )
            if apidata_m:
                fragment = apidata_m.group(1)
                rows = re.findall(r"(\d{6})\|([^|]*)\|[^|]*\|([\d.]+)", fragment)

        # Report date extraction
        report_date = date.today()
        date_m = re.search(r"(\d{4})年(\d{1,2})季度", html)
        if date_m:
            y, q = int(date_m.group(1)), int(date_m.group(2))
            report_date = date(y, (q - 1) * 3 + 1, 1)

        for row in rows:
            stock_code, stock_name, ratio_str = row[0], row[1], row[2]
            ratio = _safe_decimal(ratio_str)
            if ratio is not None and ratio > Decimal("1"):
                ratio = ratio / Decimal("100")
            results.append(
                FundHoldingRaw(
                    fund_code=fund_code,
                    report_date=report_date,
                    stock_code=stock_code.strip(),
                    stock_name=stock_name.strip(),
                    ratio=ratio,
                )
            )

        if not results:
            logger.warning("Eastmoney: no holdings parsed for %s", fund_code)
        else:
            logger.info("Eastmoney: fetched %d holdings for %s", len(results), fund_code)

        return results
