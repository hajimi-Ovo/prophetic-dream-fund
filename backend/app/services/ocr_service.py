"""
OCR Service — extract fund-holding information from uploaded images.

Provides a functional regex-based fallback when PaddleOCR is not available.
The ``recognize`` method accepts raw image bytes, runs text extraction
(optionally via PaddleOCR), and then parses fund codes / amounts / shares
from the resulting text lines.

Image-preprocessing stubs are included for future enhancement:
- grayscale conversion
- contrast enhancement
- tilt correction
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class OcrHoldingItem:
    """Parsed holding extracted from an OCR result."""

    fund_code: str | None = None
    fund_name: str | None = None
    amount: Decimal | None = None
    shares: Decimal | None = None
    confidence: float = 0.0
    raw_line: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_code": self.fund_code,
            "fund_name": self.fund_name,
            "amount": str(self.amount) if self.amount is not None else None,
            "shares": str(self.shares) if self.shares is not None else None,
            "confidence": self.confidence,
            "raw_line": self.raw_line,
        }


@dataclass
class OcrResult:
    """Overall OCR result containing parsed items and raw text."""

    raw_text: str = ""
    items: list[OcrHoldingItem] = field(default_factory=list)
    overall_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "items": [item.to_dict() for item in self.items],
            "overall_confidence": self.overall_confidence,
        }


# ---------------------------------------------------------------------------
# Regex patterns for field extraction
# ---------------------------------------------------------------------------

# Fund code: exactly 6 digits, commonly preceded by "基金代码" or similar
_RE_FUND_CODE = re.compile(
    r"(?:基金代码|代码|code)[：:\s]*(\d{6})",
    re.IGNORECASE,
)

# Standalone 6-digit code (more aggressive fallback)
_RE_CODE_FALLBACK = re.compile(r"\b(\d{6})\b")

# Amount: ¥ prefix or "金额" / "买入金额" followed by a number
_RE_AMOUNT = re.compile(
    r"(?:¥|￥|CNY|金额|买入金额|投入金额|成交金额)[：:\s]*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
# Alternate: number preceded by ¥ symbol directly
_RE_AMOUNT_CURRENCY = re.compile(r"[¥￥]\s*([\d,]+\.?\d*)")

# Shares: "份" suffix or "份额" / "持有份额"
_RE_SHARES = re.compile(
    r"(?:份额|持有份额|成交份额|数量)[：:\s]*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
# Alternate: number followed by 份
_RE_SHARES_SUFFIX = re.compile(r"([\d,]+\.?\d*)\s*份")

# Fund name: common Chinese fund name pattern
_RE_FUND_NAME = re.compile(
    r"(?:基金名称|名称|name)[：:\s]*(.+?)(?:\s|$)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class OcrService:
    """
    OCR service for extracting fund-holding information from images.

    Attempts to use PaddleOCR if installed; otherwise falls back to
    regex-based text parsing (functional stub).
    """

    # ------------------------------------------------------------------
    # Image preprocessing stubs
    # ------------------------------------------------------------------

    def _to_grayscale(self, image_bytes: bytes) -> bytes:
        """
        Convert image to grayscale.

        Stub: returns input as-is.  Replace with OpenCV / Pillow processing
        when image-quality improvement is needed.
        """
        logger.debug("Grayscale conversion — stub, returning original bytes")
        return image_bytes

    def _enhance_contrast(self, image_bytes: bytes) -> bytes:
        """
        Enhance image contrast.

        Stub: returns input as-is.  Replace with OpenCV / Pillow processing
        when image-quality improvement is needed.
        """
        logger.debug("Contrast enhancement — stub, returning original bytes")
        return image_bytes

    def _correct_tilt(self, image_bytes: bytes) -> bytes:
        """
        Correct image tilt / skew.

        Stub: returns input as-is.  Replace with OpenCV / Pillow processing
        when image-quality improvement is needed.
        """
        logger.debug("Tilt correction — stub, returning original bytes")
        return image_bytes

    # ------------------------------------------------------------------
    # Text recognition
    # ------------------------------------------------------------------

    async def recognize(self, image_bytes: bytes) -> OcrResult:
        """
        Run OCR on *image_bytes* and return structured results.

        Attempts PaddleOCR first; falls back to a no-op stub that signals
        the caller to provide raw text directly.
        """
        # Preprocessing pipeline (all stubs for now)
        preprocessed = image_bytes
        preprocessed = self._to_grayscale(preprocessed)
        preprocessed = self._enhance_contrast(preprocessed)
        preprocessed = self._correct_tilt(preprocessed)

        raw_text: str = ""

        # Try PaddleOCR
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]

            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            result = ocr.ocr(preprocessed, cls=True)
            if result and result[0]:
                lines = [line[1][0] for line in result[0]]
                raw_text = "\n".join(lines)
                logger.info("PaddleOCR extracted %d text lines", len(lines))
            else:
                logger.warning("PaddleOCR returned empty result")

        except ImportError:
            logger.debug("PaddleOCR not installed — using stub text extraction")
        except Exception:
            logger.exception("PaddleOCR recognition failed — using stub")

        # Parse fields from raw text
        items = self.parse_fields(raw_text) if raw_text else []

        overall_confidence = (
            sum(item.confidence for item in items) / len(items)
            if items
            else 0.0
        )

        return OcrResult(
            raw_text=raw_text,
            items=items,
            overall_confidence=overall_confidence,
        )

    # ------------------------------------------------------------------
    # Field parsing
    # ------------------------------------------------------------------

    def parse_fields(self, raw_text: str) -> list[OcrHoldingItem]:
        """
        Extract fund_code (6 digits), amounts (¥xxx), shares (xxx份)
        from *raw_text* using regex patterns.

        Returns a list of ``OcrHoldingItem``, one per detected fund.
        """
        if not raw_text or not raw_text.strip():
            return []

        # Strategy: split text into logical blocks (e.g. by empty lines or
        # lines that look like fund-name headers), then parse each block.
        lines = raw_text.strip().splitlines()
        blocks = self._split_into_blocks(lines)

        items: list[OcrHoldingItem] = []
        for block_lines in blocks:
            block_text = "\n".join(block_lines)
            item = self._parse_block(block_text)
            if item.fund_code or item.fund_name:
                items.append(item)
            elif block_text.strip():
                # Try single-line parsing as last resort
                item = self._parse_line(block_text.strip())
                if item and (item.fund_code or item.fund_name):
                    items.append(item)

        # Deduplicate by fund_code
        seen: set[str] = set()
        deduped: list[OcrHoldingItem] = []
        for item in items:
            key = item.fund_code or ""
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            deduped.append(item)

        logger.info(
            "Parsed %d fund items from %d chars of text",
            len(deduped),
            len(raw_text),
        )
        return deduped

    # ------------------------------------------------------------------
    # Block / line helpers
    # ------------------------------------------------------------------

    def _split_into_blocks(self, lines: list[str]) -> list[list[str]]:
        """
        Split OCR lines into logical blocks separated by empty lines
        or lines that start a new fund entry (e.g. contain "基金" or "代码").
        """
        blocks: list[list[str]] = []
        current: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    blocks.append(current)
                    current = []
                continue

            # Detect start of a new fund record.
            # Only "基金代码" or standalone "代码" triggers a new block;
            # fields like "基金名称" belong to the current entry.
            if current and re.search(
                r"基金代码|代码[：:]|^[：:]?\s*基金\b|持仓|持有",
                stripped,
            ):
                blocks.append(current)
                current = []

            current.append(stripped)

        if current:
            blocks.append(current)

        return blocks

    def _parse_block(self, text: str) -> OcrHoldingItem:
        """Parse a block of text into a single holding item."""
        fund_code = None
        fund_name = None
        amount = None
        shares = None
        confidence = 0.0

        # Extract fund code
        m = _RE_FUND_CODE.search(text)
        if m:
            fund_code = m.group(1)
            confidence += 0.4
        else:
            # Fallback: find any 6-digit number
            codes = _RE_CODE_FALLBACK.findall(text)
            if codes:
                fund_code = codes[0]
                confidence += 0.2

        # Extract amount
        m = _RE_AMOUNT.search(text)
        if m:
            try:
                amount = Decimal(m.group(1).replace(",", ""))
                confidence += 0.3
            except Exception:
                pass
        else:
            m = _RE_AMOUNT_CURRENCY.search(text)
            if m:
                try:
                    amount = Decimal(m.group(1).replace(",", ""))
                    confidence += 0.25
                except Exception:
                    pass

        # Extract shares
        m = _RE_SHARES.search(text)
        if m:
            try:
                shares = Decimal(m.group(1).replace(",", ""))
                confidence += 0.3
            except Exception:
                pass
        else:
            m = _RE_SHARES_SUFFIX.search(text)
            if m:
                try:
                    shares = Decimal(m.group(1).replace(",", ""))
                    confidence += 0.25
                except Exception:
                    pass

        # Extract fund name
        m = _RE_FUND_NAME.search(text)
        if m and m.group(1).strip():
            fund_name = m.group(1).strip()
            confidence += 0.2

        return OcrHoldingItem(
            fund_code=fund_code,
            fund_name=fund_name,
            amount=amount,
            shares=shares,
            confidence=min(confidence, 1.0),
            raw_line=text[:200],
        )

    def _parse_line(self, line: str) -> OcrHoldingItem | None:
        """Parse a single line as a last-resort attempt."""
        code_m = _RE_CODE_FALLBACK.search(line)
        if not code_m:
            return None

        fund_code = code_m.group(1)
        confidence = 0.3

        # Try to find amount / shares in the same line
        amount = None
        shares = None
        amt_m = _RE_AMOUNT_CURRENCY.search(line)
        if amt_m:
            try:
                amount = Decimal(amt_m.group(1).replace(",", ""))
                confidence += 0.25
            except Exception:
                pass

        sh_m = _RE_SHARES_SUFFIX.search(line)
        if sh_m:
            try:
                shares = Decimal(sh_m.group(1).replace(",", ""))
                confidence += 0.25
            except Exception:
                pass

        return OcrHoldingItem(
            fund_code=fund_code,
            fund_name=None,
            amount=amount,
            shares=shares,
            confidence=min(confidence, 1.0),
            raw_line=line[:200],
        )
