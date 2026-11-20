"""procurement v2: savings ledger and contract metadata

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTRACT_COLUMNS = ("supplier", "category", "estimated_annual_cost")
PREDICATE = "company_id = NULLIF(current_setting('praxis.company_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "savings_entries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("supplier", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("baseline_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("annualized_savings", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column("contracts", sa.Column("supplier", sa.Text(), nullable=True))
    op.add_column("contracts", sa.Column("category", sa.String(80), nullable=True))
    op.add_column("contracts", sa.Column("estimated_annual_cost", sa.Numeric(14, 2), nullable=True))
    op.execute("ALTER TABLE savings_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE savings_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON savings_entries USING ({PREDICATE}) "
        f"WITH CHECK ({PREDICATE})"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON savings_entries TO praxis_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON savings_entries")
    for column in reversed(CONTRACT_COLUMNS):
        op.drop_column("contracts", column)
    op.drop_table("savings_entries")
