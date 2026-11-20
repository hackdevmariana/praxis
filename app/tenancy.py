"""Tenant catalogs and per-company tool activation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.context import ToolContext
from app.db.models import TenantProfileRow, ToolActivationRow
from app.db.rls import company_session
from app.registry import registry

CATALOG_PATTERNS: dict[str, tuple[str, ...]] = {
    "hotel": (
        "datetime.*",
        "finance.vat",
        "weather.forecast",
        "geo.geocode",
        "calendar.*",
        "documents.*",
        "currency.convert",
    ),
    "poligono": (
        "finance.*",
        "validate.*",
        "units.convert",
        "weather.forecast",
        "geo.geocode",
        "documents.*",
        "procurement.*",
        "alerts.contract_renewal",
    ),
    "asociacion": (
        "procurement.*",
        "finance.*",
        "validate.*",
        "documents.*",
        "alerts.contract_renewal",
        "currency.convert",
    ),
    "general": ("*",),
}


@dataclass(frozen=True, slots=True)
class TenantProfile:
    """Operational catalog and activation state for a company."""

    company_id: str
    catalog_key: str = "general"
    enabled_tools: frozenset[str] | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        try:
            UUID(self.company_id)
        except ValueError as error:
            raise ValueError("company_id debe ser un UUID") from error
        if self.catalog_key not in CATALOG_PATTERNS:
            raise ValueError(f"Catálogo desconocido: {self.catalog_key}")


class ToolAccessPolicy(Protocol):
    """Resolve the effective toolset for an execution context."""

    async def allowed_tools(self, ctx: ToolContext) -> frozenset[str] | None: ...


class AllowAllToolAccess:
    """Development/default policy: every registered tool is available."""

    async def allowed_tools(self, ctx: ToolContext) -> frozenset[str] | None:
        return None


class InMemoryToolAccessPolicy:
    """Injectable policy backed by in-process tenant profiles."""

    def __init__(self, profiles: Mapping[str, TenantProfile] | None = None) -> None:
        self._profiles = dict(profiles or {})

    async def allowed_tools(self, ctx: ToolContext) -> frozenset[str] | None:
        if ctx.company_id is None:
            return None
        profile = self._profiles.get(ctx.company_id)
        if profile is None or not profile.is_active:
            return frozenset()
        tools = catalog_tools(profile.catalog_key)
        if profile.enabled_tools is not None:
            tools = tools & profile.enabled_tools
        return frozenset(tools)


class SqlAlchemyToolAccessPolicy:
    """Policy backed by `tenant_profiles` and `tool_activations` under RLS."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def allowed_tools(self, ctx: ToolContext) -> frozenset[str] | None:
        if ctx.company_id is None:
            return None
        try:
            company_id = UUID(ctx.company_id)
        except ValueError:
            return frozenset()

        async with company_session(self._engine, company_id) as session:
            profile = await session.scalar(
                select(TenantProfileRow).where(TenantProfileRow.company_id == company_id)
            )
            if profile is None or not profile.is_active:
                return frozenset()
            catalog_key = profile.catalog_key
            activations = (
                await session.scalars(
                    select(ToolActivationRow).where(ToolActivationRow.company_id == company_id)
                )
            ).all()
            enabled = {
                row.tool_name for row in activations if row.is_enabled and not row.deprecated
            }
            disabled = {
                row.tool_name for row in activations if not row.is_enabled or row.deprecated
            }

        try:
            tools = catalog_tools(catalog_key)
        except ValueError:
            return frozenset()

        if enabled or disabled:
            tools = (tools - disabled) | (enabled & tools)
        return frozenset(tools)


def catalog_tools(catalog_key: str) -> frozenset[str]:
    try:
        patterns = CATALOG_PATTERNS[catalog_key]
    except KeyError:
        raise ValueError(f"Catálogo desconocido: {catalog_key}") from None
    return frozenset(
        name for name in registry.names() if any(fnmatchcase(name, pattern) for pattern in patterns)
    )


async def apply_tool_access(ctx: ToolContext, policy: ToolAccessPolicy) -> ToolContext:
    return replace(ctx, allowed_tools=await policy.allowed_tools(ctx))
