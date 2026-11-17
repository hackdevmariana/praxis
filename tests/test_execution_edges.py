import asyncio
import importlib
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import BaseModel

from app.audit import InMemoryExecutionLogStore, set_execution_log_store
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.execution import execute_by_name, execute_tool
from app.providers.contracts import get_contract_repository
from app.providers.documents import (
    get_document_repository,
    get_document_store,
    get_invoice_renderer,
)
from app.providers.google_calendar import UnconfiguredCalendarConnector
from app.registry import registry

importlib.import_module("app.tools")

CTX = ToolContext(
    request_id="edges",
    company_id="11111111-1111-4111-8111-111111111111",
    channel="mcp",
    scopes=frozenset({"finance.calculate"}),
)


def test_execute_by_name_resolves_registered_tool() -> None:
    envelope = asyncio.run(execute_by_name("finance.vat", {"amount": "100.00"}, CTX))

    assert envelope["success"] is True
    assert envelope["tool"] == "finance.vat"


def test_execute_by_name_rejects_unknown_tool() -> None:
    with pytest.raises(ToolError) as error:
        asyncio.run(execute_by_name("missing.tool", {}, CTX))

    assert error.value.code == ErrorCode.TOOL_NOT_AVAILABLE


def test_unexpected_handler_failure_is_audited() -> None:
    async def broken(_params: BaseModel, _ctx: ToolContext) -> BaseModel:
        raise RuntimeError("fallo inesperado")

    store = InMemoryExecutionLogStore()
    set_execution_log_store(store)
    spec = replace(registry.get("finance.vat"), handler=broken)

    with pytest.raises(RuntimeError):
        asyncio.run(execute_tool(spec, {"amount": "100.00"}, CTX))

    assert len(store.records) == 1
    assert store.records[0].success is False
    assert store.records[0].error == {"code": ErrorCode.INTERNAL_ERROR}


def test_tool_error_serializes_details() -> None:
    error = ToolError("custom", "mensaje", details={"campo": "valor"})

    assert error.to_dict() == {
        "code": "custom",
        "message": "mensaje",
        "details": {"campo": "valor"},
    }


def test_unconfigured_providers_fail_closed() -> None:
    connector = UnconfiguredCalendarConnector()
    repository = get_document_repository(CTX)
    store = get_document_store(CTX)
    renderer = get_invoice_renderer(CTX)
    document_id = UUID("33333333-3333-4333-8333-333333333333")

    with pytest.raises(ToolError) as calendar_error:
        asyncio.run(
            connector.list_events(
                calendar_id="primary",
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 1, 2, tzinfo=UTC),
                max_results=10,
            )
        )
    with pytest.raises(ToolError) as document_error:
        asyncio.run(repository.get(company_id=CTX.company_id or "", document_id=document_id))
    with pytest.raises(ToolError) as store_error:
        asyncio.run(
            store.next_number(
                company_id=CTX.company_id or "",
                year=2026,
                series=None,
                document_type="invoice",
            )
        )
    with pytest.raises(ToolError) as renderer_error:
        renderer.render_pdf("<html></html>")

    assert calendar_error.value.code == "connector_not_connected"
    assert document_error.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert store_error.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert renderer_error.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert (
        asyncio.run(
            get_contract_repository(CTX).get(
                company_id=CTX.company_id or "", contract_id=document_id
            )
        )
        is None
    )
