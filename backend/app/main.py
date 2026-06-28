"""
FastAPI application entry point for 预知梦基金 (Prophetic Dream Fund).

Configures middleware, lifespan events, exception handlers, and
mounts the API router at /api/v1.
"""

import json
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.database import init_db


# ---------------------------------------------------------------------------
# Custom JSON encoder — Decimal → float, date/datetime → isoformat
# ---------------------------------------------------------------------------
def _json_serializer(obj: object) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, date | datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class _AppJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            default=_json_serializer,
        ).encode("utf-8")



# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan handler — init DB on startup."""
    # Startup
    await init_db()

    yield

    # Shutdown — nothing to clean up (SQLite closes with engine)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="预知梦基金 API",
    version="1.0.0",
    description="Personal investment fund platform — Prophetic Dream Fund",
    lifespan=lifespan,
    default_response_class=_AppJSONResponse,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API Router
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Global exception handlers — return unified {code, message, data} format
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions."""
    return _AppJSONResponse(
        status_code=500,
        content={
            "code": -1,
            "message": f"Internal server error: {exc!s}",
            "data": None,
        },
    )


# ---------------------------------------------------------------------------
# Root health check (at app root, independent of API versioning)
# ---------------------------------------------------------------------------
@app.get("/health")
async def root_health() -> dict[str, Any]:
    """Health-check endpoint returning the unified response format."""
    return {
        "code": 0,
        "message": "ok",
        "data": {"service": "prophetic-dream-fund"},
    }
