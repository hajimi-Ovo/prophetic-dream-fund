"""initial_all_tables

Revision ID: 001
Revises:
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. funds
    # ------------------------------------------------------------------
    op.create_table(
        "funds",
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("scale", sa.Numeric(18, 4), nullable=True),
        sa.Column("fee_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("company", sa.String(100), nullable=True),
        sa.Column("inception_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )

    # ------------------------------------------------------------------
    # 2. fund_navs
    # ------------------------------------------------------------------
    op.create_table(
        "fund_navs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("nav", sa.Numeric(10, 4), nullable=False),
        sa.Column("accumulated_nav", sa.Numeric(10, 4), nullable=True),
        sa.Column("daily_return", sa.Numeric(10, 6), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["fund_code"], ["funds.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_code", "date", name="uq_fund_nav_code_date"),
    )

    # ------------------------------------------------------------------
    # 3. fund_holdings
    # ------------------------------------------------------------------
    op.create_table(
        "fund_holdings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(10), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("stock_code", sa.String(10), nullable=True),
        sa.Column("stock_name", sa.String(100), nullable=True),
        sa.Column("ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["fund_code"], ["funds.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fund_code", "report_date", "stock_code",
            name="uq_fund_holding_code_date_stock",
        ),
    )

    # ------------------------------------------------------------------
    # 4. fund_managers
    # ------------------------------------------------------------------
    op.create_table(
        "fund_managers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("tenure_return", sa.Numeric(10, 4), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["fund_code"], ["funds.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 5. holdings
    # ------------------------------------------------------------------
    op.create_table(
        "holdings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(10), nullable=False),
        sa.Column("fund_name", sa.String(100), nullable=False),
        sa.Column("buy_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("shares", sa.Numeric(18, 4), nullable=False),
        sa.Column("buy_nav", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 6. fund_transactions
    # ------------------------------------------------------------------
    op.create_table(
        "fund_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("holding_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("shares", sa.Numeric(18, 4), nullable=False),
        sa.Column("price", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "type IN ('buy', 'sell')",
            name="ck_fund_transaction_type",
        ),
        sa.ForeignKeyConstraint(
            ["holding_id"], ["holdings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 7. fund_watchlists
    # ------------------------------------------------------------------
    op.create_table(
        "fund_watchlists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(10), nullable=False),
        sa.Column("fund_name", sa.String(100), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_code"),
    )

    # ------------------------------------------------------------------
    # 8. risk_profiles
    # ------------------------------------------------------------------
    op.create_table(
        "risk_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("risk_tolerance", sa.String(20), nullable=False),
        sa.Column("investment_horizon", sa.String(20), nullable=False),
        sa.Column("return_expectation", sa.String(20), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 9. recommendation_logs
    # ------------------------------------------------------------------
    op.create_table(
        "recommendation_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(10), nullable=False),
        sa.Column("score", sa.Numeric(10, 2), nullable=True),
        sa.Column("strategy", sa.String(30), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 10. data_source_logs
    # ------------------------------------------------------------------
    op.create_table(
        "data_source_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(50), nullable=True),
        sa.Column("fetch_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("data_source_logs")
    op.drop_table("recommendation_logs")
    op.drop_table("risk_profiles")
    op.drop_table("fund_watchlists")
    op.drop_table("fund_transactions")
    op.drop_table("holdings")
    op.drop_table("fund_managers")
    op.drop_table("fund_holdings")
    op.drop_table("fund_navs")
    op.drop_table("funds")
