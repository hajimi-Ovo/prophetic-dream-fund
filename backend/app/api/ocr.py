"""
OCR API routes — upload fund-screenshots, parse holdings, confirm & batch-create.

Endpoints:
- POST /holdings/ocr        Upload an image for OCR parsing
- POST /holdings/ocr/confirm Confirm parsed results → batch create holdings
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.schemas.holding import HoldingCreate
from app.services.holding_service import HoldingService
from app.services.ocr_service import OcrService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holdings/ocr", tags=["ocr"])

# Error codes
ERR_NO_CONTENT = 30001
ERR_PARSE_FAILED = 30002
ERR_FILE_TOO_LARGE = 30003

# Max upload size: 5 MB
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class OcrConfirmItem(BaseModel):
    """Single holding item to confirm from OCR result."""

    fund_code: str = Field(..., min_length=6, max_length=6, description="6-digit fund code")
    fund_name: str | None = Field(None, description="Fund display name")
    amount: str = Field(..., description="Invested amount (CNY)")
    shares: str | None = Field(None, description="Shares held")


class OcrConfirmRequest(BaseModel):
    """Batch confirm request body."""

    items: list[OcrConfirmItem] = Field(..., min_length=1, max_length=50)
    buy_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD), defaults to today")


# ---------------------------------------------------------------------------
# POST /holdings/ocr
# ---------------------------------------------------------------------------


@router.post("")
async def ocr_upload(
    file: UploadFile,
) -> dict[str, Any]:
    """
    Upload an image and run OCR to extract fund-holding information.

    Returns structured results with fund_code, fund_name, amount, shares.
    The user can then confirm and batch-create holdings.
    """
    # Validate file size
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        return {
            "code": ERR_FILE_TOO_LARGE,
            "message": f"文件大小不能超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            "data": None,
        }
    if len(content) == 0:
        return {
            "code": ERR_NO_CONTENT,
            "message": "上传文件为空",
            "data": None,
        }

    service = OcrService()
    result = await service.recognize(content)

    if not result.items:
        return {
            "code": ERR_PARSE_FAILED,
            "message": "未能从图片中识别出基金持仓信息，请尝试手动录入",
            "data": result.to_dict(),
        }

    return {
        "code": 0,
        "message": "ok",
        "data": result.to_dict(),
    }


# ---------------------------------------------------------------------------
# POST /holdings/ocr/confirm
# ---------------------------------------------------------------------------


@router.post("/confirm", status_code=201)
async def ocr_confirm(
    body: OcrConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Confirm OCR-parsed results and batch-create holdings.

    Each item in *items* is created as a separate holding record.
    If *buy_date* is not provided, today's date is used.
    """
    from datetime import date

    holding_service = HoldingService(db)
    buy_date = body.buy_date or date.today().isoformat()

    created: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, item in enumerate(body.items):
        try:
            from decimal import Decimal

            amount = Decimal(item.amount)
            shares = Decimal(item.shares) if item.shares else Decimal("0")
            # Compute approximate buy_nav from amount and shares
            buy_nav = (amount / shares) if shares and shares != 0 else None

            holding_data = HoldingCreate(
                fund_code=item.fund_code,
                fund_name=item.fund_name or item.fund_code,
                buy_date=date.fromisoformat(buy_date),
                amount=amount,
                shares=shares,
                buy_nav=buy_nav,
            )
            holding = await holding_service.create(holding_data)
            created.append(holding)

        except Exception:
            logger.exception("Failed to create holding for item %d: %s", idx, item.fund_code)
            errors.append({
                "index": idx,
                "fund_code": item.fund_code,
                "message": "创建持仓失败",
            })

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "created_count": len(created),
            "error_count": len(errors),
            "items": created,
            "errors": errors,
        },
    }
