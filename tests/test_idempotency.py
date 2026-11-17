import asyncio
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from pydantic import BaseModel

from app import tools  # noqa: F401  # pyright: ignore[reportUnusedImport]
from app.clock import MADRID
from app.context import ToolContext
from app.errors import ToolError
from app.execution import execute_tool
from app.idempotency import (
    IdempotencyStore,
    deduplicated_value,
    scoped_key,
)
from app.providers.google_calendar import (
    CalendarPage,
    CreatedEventRecord,
    set_calendar_connector,
)
from app.registry import registry
from app.result import ToolResult
from app.tools.calendar.create_event.schemas import CreateEventInput

COMPANY_1 = "company-1"
COMPANY_2 = "company-2"
CREATED = CreatedEventRecord(
    event_id="evt_idem",
    html_link=None,
    status="confirmed",
    start="2026-11-16T10:00:00+01:00",
    end="2026-11-16T11:00:00+01:00",
    created=datetime(2026, 11, 13, 12, 0, tzinfo=MADRID),
)


class FakeConnector:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []

    async def list_events(
        self,
        *,
        calendar_id: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> CalendarPage:
        raise NotImplementedError

    async def create_event(
        self,
        *,
        calendar_id: str,
        title: str,
        start: datetime,
        end: datetime,
        description: str | None,
        location: str | None,
        attendees: Sequence[str],
        all_day: bool,
        timezone: str,
        send_notifications: bool,
        recurrence_rrule: str | None,
    ) -> CreatedEventRecord:
        self.create_calls.append({"title": title, "calendar_id": calendar_id})
        return CREATED


class SampleOutput(BaseModel):
    value: int
    deduplicated: bool = False


def _ctx(company_id: str) -> ToolContext:
    return ToolContext(
        request_id="req",
        company_id=company_id,
        confirmed=True,
        scopes=frozenset({"calendar.write"}),
    )


def _params(*, key: str, title: str = "Demo") -> CreateEventInput:
    return CreateEventInput.model_validate(
        {
            "title": title,
            "start": "2026-11-16T10:00:00+01:00",
            "end": "2026-11-16T11:00:00+01:00",
            "idempotency_key": key,
        }
    )


def _run(company_id: str, params: CreateEventInput) -> dict[str, Any]:
    spec = registry.get("calendar.create_event")
    return asyncio.run(execute_tool(spec, params, _ctx(company_id)))


def test_scoped_key_includes_tool_and_company() -> None:
    assert (
        scoped_key("calendar.create_event", COMPANY_1, "key-0001")
        == "calendar.create_event:company-1:key-0001"
    )
    assert (
        scoped_key("calendar.create_event", None, "key-0001") == "calendar.create_event::key-0001"
    )


def test_store_expires_entries() -> None:
    store = IdempotencyStore(ttl=timedelta(minutes=5))
    start = datetime(2026, 11, 13, 10, 0, tzinfo=MADRID)
    store.put("key", "value", input_hash="hash", at=start)

    assert store.get("key", at=start + timedelta(minutes=4)) is not None
    assert store.get("key", at=start + timedelta(minutes=5)) is None


def test_deduplicated_value_marks_data_and_metadata() -> None:
    result = ToolResult(
        data=SampleOutput(value=1),
        warnings=["warning"],
        metadata_extra={"source": "test", "effect": "created"},
    )

    deduped = cast(ToolResult[SampleOutput], deduplicated_value(result))

    assert isinstance(deduped.data, SampleOutput)
    assert deduped.data.deduplicated is True
    assert deduped.warnings == ["warning"]
    assert deduped.metadata_extra["effect"] == "deduplicated"


def test_same_key_with_different_input_is_conflict() -> None:
    connector = FakeConnector()
    set_calendar_connector(connector)

    first = _run(COMPANY_1, _params(key="key-0001", title="Demo"))
    with pytest.raises(ToolError) as error:
        _run(COMPANY_1, _params(key="key-0001", title="Otra reunión"))

    assert first["success"] is True
    assert error.value.code == "conflict"
    assert len(connector.create_calls) == 1


def test_same_input_with_different_key_creates_new_effect() -> None:
    connector = FakeConnector()
    set_calendar_connector(connector)

    first = _run(COMPANY_1, _params(key="key-0001"))
    second = _run(COMPANY_1, _params(key="key-0002"))

    assert first["data"]["deduplicated"] is False
    assert second["data"]["deduplicated"] is False
    assert len(connector.create_calls) == 2


def test_idempotency_is_isolated_by_company() -> None:
    connector = FakeConnector()
    set_calendar_connector(connector)

    first = _run(COMPANY_1, _params(key="key-0001"))
    second = _run(COMPANY_2, _params(key="key-0001"))

    assert first["data"]["deduplicated"] is False
    assert second["data"]["deduplicated"] is False
    assert len(connector.create_calls) == 2


def test_cached_result_keeps_traceability_metadata() -> None:
    connector = FakeConnector()
    set_calendar_connector(connector)

    first = _run(COMPANY_1, _params(key="key-0001"))
    second = _run(COMPANY_1, _params(key="key-0001"))

    assert first["metadata"]["effect"] == "created"
    assert second["metadata"]["effect"] == "deduplicated"
    assert second["metadata"]["source"] == first["metadata"]["source"]
    assert second["metadata"]["idempotency_key"] == "key-0001"
    assert len(connector.create_calls) == 1
