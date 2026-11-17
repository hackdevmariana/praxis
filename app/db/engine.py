"""Async SQLAlchemy engine factory for PRAXIS persistence."""

from __future__ import annotations

import os
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def database_url_from_env(env: Mapping[str, str] | None = None) -> str | None:
    """Return DATABASE_URL when it is configured."""
    values = os.environ if env is None else env
    return values.get("DATABASE_URL") or None


def create_db_engine(
    url: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> AsyncEngine | None:
    """Create an engine only when a database URL is available."""
    resolved = url if url is not None else database_url_from_env(env)
    if not resolved:
        return None
    return create_async_engine(resolved, pool_pre_ping=True)
