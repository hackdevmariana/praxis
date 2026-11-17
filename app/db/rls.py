"""Tenant-scoped SQLAlchemy sessions and PostgreSQL RLS helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

COMPANY_SETTING = "praxis.company_id"


async def set_company_context(session: AsyncSession, company_id: str | UUID) -> None:
    """Set the transaction-local company used by RLS policies."""
    await session.execute(
        text("SELECT set_config(:name, :value, true)"),
        {"name": COMPANY_SETTING, "value": str(company_id)},
    )


@asynccontextmanager
async def company_session(
    engine: AsyncEngine, company_id: str | UUID
) -> AsyncGenerator[AsyncSession]:
    """Open a session with the RLS company context applied."""
    async with AsyncSession(engine) as session:
        await set_company_context(session, company_id)
        try:
            yield session
        finally:
            await session.rollback()
