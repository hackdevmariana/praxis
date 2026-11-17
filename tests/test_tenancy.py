import asyncio

import pytest

from app import tools  # noqa: F401  # pyright: ignore[reportUnusedImport]
from app.context import ToolContext
from app.tenancy import (
    AllowAllToolAccess,
    InMemoryToolAccessPolicy,
    TenantProfile,
    apply_tool_access,
    catalog_tools,
)

COMPANY = "11111111-1111-4111-8111-111111111111"


def test_hotel_catalog_contains_its_tools_only() -> None:
    names = catalog_tools("hotel")

    assert "finance.vat" in names
    assert "calendar.create_event" in names
    assert "documents.extract_invoice" in names
    assert "procurement.tpv_savings" not in names


def test_poligono_catalog_contains_procurement() -> None:
    names = catalog_tools("poligono")

    assert "procurement.tpv_savings" in names
    assert "procurement.compare_offers" in names
    assert "calendar.create_event" not in names


def test_policy_intersects_catalog_and_activation() -> None:
    profile = TenantProfile(
        company_id=COMPANY,
        catalog_key="hotel",
        enabled_tools=frozenset({"finance.vat", "procurement.tpv_savings"}),
    )
    policy = InMemoryToolAccessPolicy({COMPANY: profile})

    allowed = asyncio.run(policy.allowed_tools(ToolContext(request_id="req", company_id=COMPANY)))

    assert allowed == frozenset({"finance.vat"})


def test_policy_denies_unknown_company() -> None:
    policy = InMemoryToolAccessPolicy()

    allowed = asyncio.run(policy.allowed_tools(ToolContext(request_id="req", company_id=COMPANY)))

    assert allowed == frozenset()


def test_policy_denies_inactive_company() -> None:
    profile = TenantProfile(company_id=COMPANY, is_active=False)
    policy = InMemoryToolAccessPolicy({COMPANY: profile})

    allowed = asyncio.run(policy.allowed_tools(ToolContext(request_id="req", company_id=COMPANY)))

    assert allowed == frozenset()


def test_policy_allows_all_without_tenant() -> None:
    policy = InMemoryToolAccessPolicy()

    allowed = asyncio.run(policy.allowed_tools(ToolContext(request_id="req")))

    assert allowed is None


def test_allow_all_policy_is_permissive() -> None:
    allowed = asyncio.run(AllowAllToolAccess().allowed_tools(ToolContext(request_id="req")))

    assert allowed is None


def test_apply_tool_access_sets_allowed_tools() -> None:
    ctx = ToolContext(request_id="req", company_id=COMPANY)
    profile = TenantProfile(company_id=COMPANY, catalog_key="hotel")

    resolved = asyncio.run(apply_tool_access(ctx, InMemoryToolAccessPolicy({COMPANY: profile})))

    assert resolved.allowed_tools == catalog_tools("hotel")


def test_tenant_profile_validates_company_and_catalog() -> None:
    with pytest.raises(ValueError, match="UUID"):
        TenantProfile(company_id="not-a-uuid")
    with pytest.raises(ValueError, match="Catálogo desconocido"):
        TenantProfile(company_id=COMPANY, catalog_key="unknown")
