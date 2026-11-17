import asyncio
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient

from app.audit import InMemoryExecutionLogStore
from app.clock import MADRID
from app.context import ToolContext
from app.execution import execute_tool
from app.main import create_app
from app.providers.google_calendar import (
    CreatedEventRecord,
    set_calendar_connector,
)
from app.registry import registry
from app.tools.calendar.create_event.schemas import CreateEventInput

CREATED = CreatedEventRecord(
    event_id="evt_audit",
    html_link=None,
    status="confirmed",
    start="2026-11-16T10:00:00+01:00",
    end="2026-11-16T11:00:00+01:00",
    created=datetime(2026, 11, 13, 12, 0, tzinfo=MADRID),
)


class FakeConnector:
    async def list_events(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def create_event(self, **kwargs: Any) -> CreatedEventRecord:
        return CREATED


class FailingStore:
    async def record(self, entry: Any) -> None:
        raise RuntimeError("store down")


def test_successful_rest_call_is_logged() -> None:
    store = InMemoryExecutionLogStore()

    with TestClient(create_app(execution_log_store=store)) as client:
        response = client.post("/api/tools/finance.vat", json={"amount": "1000.00"})

    assert response.status_code == 200
    assert len(store.records) == 1
    record = store.records[0]
    assert record.success is True
    assert record.tool_name == "finance.vat"
    assert record.channel == "http"
    assert len(record.input_hash) == 64
    assert record.source == "deterministic"
    assert record.execution_time_ms >= 0


def test_failed_rest_call_is_logged_without_input_details() -> None:
    store = InMemoryExecutionLogStore()

    with TestClient(create_app(execution_log_store=store)) as client:
        response = client.post(
            "/api/tools/calendar.create_event",
            json={
                "title": "Visita",
                "start": "2026-11-20T10:00:00+01:00",
                "end": "2026-11-20T11:00:00+01:00",
                "idempotency_key": "visita-audit-2026",
            },
        )

    envelope = response.json()
    assert envelope["metadata"]["errors"][0]["code"] == "confirmation_required"
    assert len(store.records) == 1
    record = store.records[0]
    assert record.success is False
    assert record.error == {"code": "confirmation_required"}
    assert record.input_hash != "visita-audit-2026"
    assert "Visita" not in str(record)


def test_repeated_key_is_logged_as_idempotency_hit() -> None:
    store = InMemoryExecutionLogStore()
    set_calendar_connector(FakeConnector())

    ctx = ToolContext(
        request_id="audit-req",
        company_id="company-1",
        confirmed=True,
        scopes=frozenset({"calendar.write"}),
    )
    params = CreateEventInput.model_validate(
        {
            "title": "Demo",
            "start": "2026-11-16T10:00:00+01:00",
            "end": "2026-11-16T11:00:00+01:00",
            "idempotency_key": "audit-demo-2026",
        }
    )
    spec = registry.get("calendar.create_event")

    with TestClient(create_app(execution_log_store=store)):
        asyncio.run(execute_tool(spec, params, ctx))
        asyncio.run(execute_tool(spec, params, ctx))

    assert [record.idempotency_hit for record in store.records] == [False, True]
    assert all(record.idempotency_key is not None for record in store.records)


def test_logging_failure_does_not_break_tool() -> None:
    with TestClient(create_app(execution_log_store=FailingStore())) as client:
        response = client.post("/api/tools/finance.vat", json={"amount": "1000.00"})

    assert response.status_code == 200
    assert response.json()["success"] is True
