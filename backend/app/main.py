"""
FastAPI application entry point for 预知梦基金 (Prophetic Dream Fund).

Configures middleware, lifespan events, exception handlers, and
mounts the API router at /api/v1.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.database import init_db
from app.redis_client import close_redis, init_redis
from app.scheduler import init_scheduler, shutdown_scheduler


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """
    Application lifespan handler.

    On startup: initialise database, Redis, and scheduler.
    On shutdown: close connections and clean up resources.
    """
    # Startup
    await init_db()
    await init_redis()
    init_scheduler()

    yield

    # Shutdown
    shutdown_scheduler()
    await close_redis()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="预知梦基金 API",
    version="1.0.0",
    description="Personal investment fund platform — Prophetic Dream Fund",
    lifespan=lifespan,
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
    return JSONResponse(
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
