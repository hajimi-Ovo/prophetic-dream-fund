"""
Async SQLAlchemy database engine, session factory, and dependency.

Uses SQLite + aiosqlite for single-user local deployment.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# SQLite engine — single-file database, no connection pool needed
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables if they don't exist (idempotent)."""
    import app.models  # noqa: F401 — ensure all models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite does not enforce foreign keys by default
        await conn.execute(text("PRAGMA foreign_keys=ON"))
    logger.info("Database tables created/verified")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
