"""tool execution log

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_execution_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(20), nullable=False),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("idempotency_hit", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("result_type", sa.String(50), nullable=True),
        sa.Column(
            "warnings",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute("ALTER TABLE tool_execution_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_execution_logs FORCE ROW LEVEL SECURITY")
    predicate = "company_id = NULLIF(current_setting('praxis.company_id', true), '')::uuid"
    op.execute(
        f"CREATE POLICY tenant_isolation ON tool_execution_logs "
        f"USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tool_execution_logs TO praxis_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tool_execution_logs")
    op.drop_table("tool_execution_logs")
