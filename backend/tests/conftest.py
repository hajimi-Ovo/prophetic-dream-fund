"""
Shared fixtures for backend tests.

Provides async database sessions, HTTP test client, and Redis mock.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# Use a file-based SQLite database for testing with WAL mode for concurrency
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db?timeout=30"


# ---------------------------------------------------------------------------
# SQLite compatibility: replace BigInteger PKs with Integer for autoincrement
# ---------------------------------------------------------------------------
def _patch_sqlite_bigint_pk() -> None:
    """
    Walk every table in Base.metadata and replace BigInteger primary-key
    columns with Integer.  SQLite does not support AUTOINCREMENT on BIGINT.
    """
    for table in Base.metadata.sorted_tables:
        for col in list(table.columns):
            if isinstance(col.type, BigInteger) and col.primary_key:
                col.type = Integer()


@pytest.fixture(scope="session")
def event_loop() -> Any:
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[Any]:
    """Create the test database engine and tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Patch BigInteger PK columns for SQLite compatibility
    _patch_sqlite_bigint_pk()

    # Enable WAL mode before creating tables (must be outside transaction)
    async with engine.connect() as conn:
        await conn.run_sync(
            lambda c: c.exec_driver_sql("PRAGMA journal_mode=WAL")
        )
        await conn.commit()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for a single test."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    """Provide an HTTP test client with the test DB dependency overridden."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
