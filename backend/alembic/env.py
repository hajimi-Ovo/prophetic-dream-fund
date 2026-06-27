"""
Alembic environment configuration for async SQLAlchemy.

This module is invoked by Alembic to set up the migration context.
It imports all ORM models so that --autogenerate can detect schema changes.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config object
config = context.config

# Set up Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so their metadata is registered on Base
# noqa ensures the imports are not flagged as unused — they are needed
# for Alembic's autogenerate to discover the model definitions.
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402, F401
    DataSourceLog,
    Fund,
    FundHolding,
    FundManager,
    FundNav,
    FundTransaction,
    FundWatchlist,
    Holding,
    RecommendationLog,
    RiskProfile,
)

# target_metadata holds the SQLAlchemy MetaData used for migrations
target_metadata = Base.metadata

# Read database URL from app config (rather than alembic.ini)
from app.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Configures the context with just a URL, not an Engine.
    Calls to context.execute() emit the given SQL string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations inside a connection context."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using an async engine.

    In this mode we create an AsyncEngine and run the migrations
    inside a connection obtained from it.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (async) migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
