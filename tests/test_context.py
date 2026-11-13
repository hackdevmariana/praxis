from dataclasses import FrozenInstanceError

import pytest

from app.context import ToolContext


def test_context_defaults_for_deterministic_tools() -> None:
    context = ToolContext(request_id="req-1")

    assert context.channel == "mcp"
    assert context.company_id is None
    assert context.scopes == frozenset()
    assert not context.has_scope("finance.calculate")


def test_context_carries_tenant_identity_and_scopes() -> None:
    context = ToolContext(
        request_id="req-2",
        user_id="user-1",
        company_id="company-1",
        role="admin",
        channel="api",
        scopes=frozenset({"finance.calculate", "validation.check"}),
    )

    assert context.has_scope("finance.calculate")
    assert not context.has_scope("documents.write")


def test_context_is_immutable() -> None:
    context = ToolContext(request_id="req-3")

    with pytest.raises(FrozenInstanceError):
        context.request_id = "req-4"  # type: ignore[misc]
