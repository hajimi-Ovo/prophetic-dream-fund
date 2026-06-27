"""
Tiantian (天天基金) data-source adapter.

Implements BaseAdapter using public Eastmoney / Tiantian HTTP APIs.
Every HTTP call is wrapped in try/except to gracefully degrade when
external services are unavailable.
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
_FUND_LIST_URL = (
    "http://fund.eastmoney.com/data/rankhandler.aspx"
    "?op=ph&dt=kf&ft=all&rs=&gs=0&sc=zzf&st=desc&pi=1&pn=10000"
)
_NAV_URL = "https://api.fund.eastmoney.com/f10/lsjz"
_DETAIL_URL = "http://fund.eastmoney.com/pingzhongdata/{code}.js"
_HOLDINGS_URL = (
    "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
    "?type=jjcc&code={code}&topline=10&year=&month="
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "http://fund.eastmoney.com/",
}

# Fund-type mapping: Eastmoney Chinese labels → English codes
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
    "LOF": "other",
    "FOF": "other",
    "保本型": "other",
    "短期理财": "money",
    "商品(黄金)": "other",
    "另类投资": "other",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
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
class TiantianAdapter(BaseAdapter):
    """Data adapter for 天天基金 (public Eastmoney API)."""

    @property
    def source_name(self) -> str:
        return "tiantian"

    @property
    def _base_url(self) -> str:
        return "http://fund.eastmoney.com/"

    # -- Fund list ----------------------------------------------------------

    async def fetch_fund_list(self) -> list[FundRaw]:
        """
        Fetch the complete fund list from the Eastmoney rank handler.

        The response is JSONP (``var rankData={...};``).  We strip the
        wrapper and parse the embedded JSON to extract per-fund rows.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
                resp = await client.get(_FUND_LIST_URL)
                resp.raise_for_status()
                text = resp.text
        except Exception:
            logger.exception("Failed to fetch fund list from %s", _FUND_LIST_URL)
            return []

        # Strip JSONP wrapper  "var rankData=...;"
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            logger.warning("Could not extract JSON from fund-list response")
            return []

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            logger.exception("Failed to parse fund-list JSON")
            return []

        results: list[FundRaw] = []
        # Each entry in ``datas`` is a pipe-delimited string;
        # columns: code, name, type, fund_scale, …, date, daily_return, …
        # The exact column order is empirical; we extract what we can.
        rows = data.get("datas", [])
        if isinstance(rows, str):
            rows = rows.split("|")  # sometimes a flat pipe string

        for row in rows:
            if not isinstance(row, str):
                continue
            cols = row.split(",")
            if len(cols) < 4:
                continue
            code = cols[0].strip()
            name = cols[1].strip()
            # Column 2 is Pinyin abbreviation; column 3 is the CN type label
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

        logger.info("Tiantian: fetched %d funds from rank list", len(results))
        return results

    # -- NAV history --------------------------------------------------------

    async def fetch_nav(
        self, fund_code: str, start_date: date, end_date: date
    ) -> list[NavRaw]:
        """
        Fetch unit NAV history from the Eastmoney F10 JSON API.

        Paginates through all available pages within the date range.
        """
        results: list[NavRaw] = []
        page = 1
        page_size = 100

        async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
            while True:
                try:
                    resp = await client.get(
                        _NAV_URL,
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
                        "Failed to fetch NAV for %s (page %d)", fund_code, page
                    )
                    break

                if data.get("ErrCode") != 0:
                    logger.warning(
                        "NAV API returned error for %s: %s",
                        fund_code,
                        data.get("ErrMsg", "unknown"),
                    )
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
            "Tiantian: fetched %d NAV records for %s (%s → %s)",
            len(results),
            fund_code,
            start_date,
            end_date,
        )
        return results

    # -- Fund detail --------------------------------------------------------

    async def fetch_fund_detail(self, fund_code: str) -> FundDetailRaw | None:
        """
        Fetch fund metadata from the Eastmoney pingzhongdata JS endpoint.

        The response is a JS variable assignment from which we extract
        manager name, company, scale, inception date, and fees.
        """
        url = _DETAIL_URL.format(code=fund_code)
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                text = resp.text
        except Exception:
            logger.exception("Failed to fetch detail for %s", fund_code)
            return None

        # Extract individual JS variables with regex
        def _js_str(key: str) -> str | None:
            m = re.search(
                rf'var\s+{key}\s*=\s*"(.*?)";', text
            )
            return m.group(1) if m else None

        def _js_num(key: str) -> Decimal | None:
            m = re.search(rf"var\s+{key}\s*=\s*\"?([\d.]+)\"?;", text)
            return _safe_decimal(m.group(1)) if m else None

        name = _js_str("fS_name")
        company = _js_str("fS_company")
        _safe_date(_js_str("fS_startdate"))
        _js_str("fS_buy")  # not actual scale; try alternate
        # Actual fund scale is often in Data_fundSharesPositions or similar
        scale_m = re.search(
            r'var\s+Data_fundSharesPositions\s*=\s*\{.*?"scl":"?([\d.]+)', text
        )
        scale: Decimal | None = None
        if scale_m:
            scale = _safe_decimal(scale_m.group(1))  # value in 万份
            if scale is not None:
                scale = scale * 10000  # convert to raw units

        # Manager info  (Data_fundManager)
        mgr_m = re.search(
            r'var\s+Data_fundManager\s*=\s*\[(.*?)\];', text, re.DOTALL
        )
        manager_name: str | None = None
        manager_start_date: date | None = None
        manager_tenure_return: Decimal | None = None
        if mgr_m:
            mgr_json = mgr_m.group(1)
            try:
                mgr = json.loads(mgr_json)[0]  # take primary manager
                manager_name = mgr.get("name")
                manager_start_date = _safe_date(mgr.get("startDate"))
                # tenure return as string percentage
                tr = mgr.get("yieldse", "")
                if tr and tr != "--":
                    with contextlib.suppress(Exception):
                        manager_tenure_return = Decimal(str(tr))
            except (json.JSONDecodeError, IndexError):
                pass

        # Fee: often in Data_rateInManager  (management fee)
        fee_rate: Decimal | None = _js_num("Data_rateInManager")

        logger.info("Tiantian: fetched detail for %s", fund_code)
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
        Fetch top-10 holdings from the FundArchivesDatas HTML/JSON endpoint.

        The Eastmoney holdings page returns HTML with embedded data tables.
        We attempt to parse the tab-delimited content from the response.
        """
        url = _HOLDINGS_URL.format(code=fund_code)
        results: list[FundHoldingRaw] = []

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception:
            logger.exception("Failed to fetch holdings for %s", fund_code)
            return results

        # Extract the embedded HTML table rows
        # Pattern: <tr><td>stock_code</td><td>stock_name</td><td>ratio</td>...
        rows = re.findall(
            r"<tr>\s*<td[^>]*>\s*(\d{6})\s*</td>\s*<td[^>]*>\s*([^<]+)\s*</td>\s*<td[^>]*>\s*([\d.]+)%?\s*</td>",
            html,
        )

        # Fallback: try the "content" div approach where data might be pipe-delimited
        if not rows:
            content_m = re.search(
                r'var\s+apidata\s*=\s*\{.*?"content":"(.*?)"', html, re.DOTALL
            )
            if content_m:
                # Content is HTML fragment with pipe-delimited fields
                fragment = content_m.group(1)
                # Try to parse table rows from the fragment
                rows = re.findall(
                    r"(\d{6})\|([^|]*)\|[^|]*\|([\d.]+)",
                    fragment,
                )

        # Attempt to find report date
        report_date = date.today()
        date_m = re.search(r"(\d{4})年(\d{1,2})季度", html)
        if date_m:
            y, q = int(date_m.group(1)), int(date_m.group(2))
            report_date = date(y, (q - 1) * 3 + 1, 1)

        for row in rows:
            stock_code, stock_name, ratio_str = row[0], row[1], row[2]
            ratio = _safe_decimal(ratio_str)
            if ratio is not None and ratio > Decimal("1"):
                # Ratios from this page are typically percentages (e.g. 5.23)
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
            logger.warning("Tiantian: no holdings parsed for %s", fund_code)
        else:
            logger.info("Tiantian: fetched %d holdings for %s", len(results), fund_code)

        return results
