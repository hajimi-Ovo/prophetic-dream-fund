"""
Async SQLAlchemy database engine, session factory, and dependency.

Provides the core database infrastructure for the application.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# Build engine kwargs based on database type
_engine_kwargs: dict = {"echo": settings.APP_DEBUG}

if "postgresql" in settings.DATABASE_URL or "asyncpg" in settings.DATABASE_URL:
    _engine_kwargs.update(
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

# Async engine bound to the configured DATABASE_URL
engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# Async session factory — callers use async_sessionmaker context
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Declarative base for all ORM models.

    Inherit from this class to register a model with SQLAlchemy's
    metadata and enable Alembic autogenerate.
    """

    pass


async def init_db() -> None:
    """Create all tables (for SQLite/dev — production uses Alembic migrations)."""
    import app.models  # noqa: F401 — ensure all models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.

    The session is automatically closed when the request completes,
    even if an exception occurs.
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
