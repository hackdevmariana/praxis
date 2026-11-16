import asyncio
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.clock import MADRID
from app.context import ToolContext
from app.errors import ToolError
from app.providers.google_calendar import (
    CalendarEventRecord,
    CalendarPage,
    CreatedEventRecord,
    set_calendar_connector,
)
from app.tools.calendar.create_event.schemas import (
    CreateEventInput,
    CreateEventOutput,
)
from app.tools.calendar.create_event.tool import create_event
from app.tools.calendar.list_events.schemas import ListEventsInput, ListEventsOutput
from app.tools.calendar.list_events.tool import list_events

CTX = ToolContext(request_id="test", company_id="company-1", confirmed=True)

EVENTS = (
    CalendarEventRecord(
        id="evt_001",
        title="Reunión de equipo",
        start="2026-11-13T09:00:00+01:00",
        end="2026-11-13T10:00:00+01:00",
        location="Sala 1",
        attendees=("ana@example.com", "luis@example.com"),
        status="confirmed",
        is_all_day=False,
        html_link="https://calendar.google.com/event?eid=evt_001",
    ),
    CalendarEventRecord(
        id="evt_002",
        title="Comida con cliente",
        start="2026-11-13T13:00:00+01:00",
        end="2026-11-13T14:30:00+01:00",
        location="Restaurante X",
        attendees=("ana@example.com",),
        status="tentative",
        is_all_day=False,
        html_link="https://calendar.google.com/event?eid=evt_002",
    ),
    CalendarEventRecord(
        id="evt_003",
        title="Festivo local",
        start="2026-11-14",
        end="2026-11-15",
        location=None,
        attendees=(),
        status="confirmed",
        is_all_day=True,
        html_link=None,
    ),
)

CREATED = CreatedEventRecord(
    event_id="evt_abc123",
    html_link="https://calendar.google.com/event?eid=evt_abc123",
    status="confirmed",
    start="2026-11-16T10:00:00+01:00",
    end="2026-11-16T11:00:00+01:00",
    created=datetime(2026, 11, 13, 12, 0, tzinfo=MADRID),
)


class FakeCalendarConnector:
    def __init__(self, created: CreatedEventRecord = CREATED) -> None:
        self.created = created
        self.list_calls: list[dict[str, Any]] = []
        self.create_calls: list[dict[str, Any]] = []

    async def list_events(
        self,
        *,
        calendar_id: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> CalendarPage:
        self.list_calls.append(
            {
                "calendar_id": calendar_id,
                "start": start,
                "end": end,
                "max_results": max_results,
            }
        )
        return CalendarPage(events=EVENTS)

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
        self.create_calls.append(
            {
                "calendar_id": calendar_id,
                "title": title,
                "start": start,
                "end": end,
                "description": description,
                "location": location,
                "attendees": list(attendees),
                "all_day": all_day,
                "timezone": timezone,
                "send_notifications": send_notifications,
                "recurrence_rrule": recurrence_rrule,
            }
        )
        return self.created


class ExpiredCalendarConnector(FakeCalendarConnector):
    async def list_events(
        self,
        *,
        calendar_id: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> CalendarPage:
        raise ToolError("connector_auth_expired", "Token revocado")

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
        raise ToolError("connector_auth_expired", "Token revocado")


def run_list(**kwargs: object) -> ListEventsOutput:
    return asyncio.run(list_events(ListEventsInput.model_validate(kwargs), CTX)).data


def run_create(**kwargs: object) -> CreateEventOutput:
    return asyncio.run(create_event(CreateEventInput.model_validate(kwargs), CTX)).data


def test_list_events_golden() -> None:
    connector = FakeCalendarConnector()
    set_calendar_connector(connector)

    output = run_list(
        start="2026-11-13T00:00:00+01:00",
        end="2026-11-14T00:00:00+01:00",
        max_results=10,
    )

    assert [event.id for event in output.events] == ["evt_001", "evt_002"]
    assert output.events[0].title == "Reunión de equipo"
    assert output.events[0].attendees == ["ana@example.com", "luis@example.com"]
    assert output.events[1].status == "tentative"
    assert output.next_page_token is None
    assert output.timezone == "Europe/Madrid"
    assert connector.list_calls[0]["calendar_id"] == "primary"


def test_list_events_includes_all_day_and_filters_non_overlap() -> None:
    connector = FakeCalendarConnector()
    set_calendar_connector(connector)

    output = run_list(
        start="2026-11-14T00:00:00+01:00",
        end="2026-11-15T00:00:00+01:00",
    )

    assert [event.id for event in output.events] == ["evt_003"]
    assert output.events[0].is_all_day is True
    assert output.events[0].start == "2026-11-14"
    assert output.events[0].end == "2026-11-15"


def test_list_events_partial_overlap_is_included() -> None:
    connector = FakeCalendarConnector()
    set_calendar_connector(connector)

    output = run_list(
        start="2026-11-13T09:30:00+01:00",
        end="2026-11-13T12:00:00+01:00",
    )

    assert [event.id for event in output.events] == ["evt_001"]


def test_list_events_uses_short_cache() -> None:
    connector = FakeCalendarConnector()
    set_calendar_connector(connector)
    payload = {
        "start": "2026-11-13T00:00:00+01:00",
        "end": "2026-11-14T00:00:00+01:00",
    }

    run_list(**payload)
    run_list(**payload)

    assert len(connector.list_calls) == 1


def test_list_events_without_connector_fails_closed() -> None:
    with pytest.raises(ToolError) as error:
        run_list(
            start="2026-11-13T00:00:00+01:00",
            end="2026-11-14T00:00:00+01:00",
        )

    assert error.value.code == "connector_not_connected"


def test_list_events_expired_token() -> None:
    set_calendar_connector(ExpiredCalendarConnector())

    with pytest.raises(ToolError) as error:
        run_list(
            start="2026-11-13T00:00:00+01:00",
            end="2026-11-14T00:00:00+01:00",
        )

    assert error.value.code == "connector_auth_expired"


def test_list_events_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        ListEventsInput.model_validate(
            {
                "start": "2026-11-14T00:00:00+01:00",
                "end": "2026-11-13T00:00:00+01:00",
            }
        )


def test_list_events_rejects_invalid_max_results() -> None:
    with pytest.raises(ValidationError):
        ListEventsInput.model_validate(
            {
                "start": "2026-11-13T00:00:00+01:00",
                "end": "2026-11-14T00:00:00+01:00",
                "max_results": 0,
            }
        )


def test_create_event_golden() -> None:
    connector = FakeCalendarConnector()
    set_calendar_connector(connector)

    output = run_create(
        title="Demo PRAXIS",
        start="2026-11-16T10:00:00+01:00",
        end="2026-11-16T11:00:00+01:00",
        attendees=["ana@example.com"],
        send_notifications=False,
        idempotency_key="demo-2026-11-16",
    )

    assert output.event_id == "evt_abc123"
    assert output.status == "confirmed"
    assert output.start == "2026-11-16T10:00:00+01:00"
    assert output.deduplicated is False
    assert connector.create_calls[0]["attendees"] == ["ana@example.com"]
    assert connector.create_calls[0]["send_notifications"] is False


def test_create_event_requires_confirmation() -> None:
    connector = FakeCalendarConnector()
    set_calendar_connector(connector)
    unconfirmed = ToolContext(request_id="test", company_id="company-1")

    with pytest.raises(ToolError) as error:
        asyncio.run(
            create_event(
                CreateEventInput.model_validate(
                    {
                        "title": "Demo",
                        "start": "2026-11-16T10:00:00+01:00",
                        "end": "2026-11-16T11:00:00+01:00",
                        "idempotency_key": "demo-2026-11-16",
                    }
                ),
                unconfirmed,
            )
        )

    assert error.value.code == "confirmation_required"
    assert connector.create_calls == []


def test_create_event_is_idempotent() -> None:
    connector = FakeCalendarConnector()
    set_calendar_connector(connector)
    payload = {
        "title": "Demo PRAXIS",
        "start": "2026-11-16T10:00:00+01:00",
        "end": "2026-11-16T11:00:00+01:00",
        "idempotency_key": "demo-2026-11-16",
    }

    first = run_create(**payload)
    second = run_create(**payload)

    assert first.deduplicated is False
    assert second.deduplicated is True
    assert second.event_id == first.event_id
    assert len(connector.create_calls) == 1


def test_create_event_all_day_uses_dates() -> None:
    connector = FakeCalendarConnector(
        created=CreatedEventRecord(
            event_id="evt_vac001",
            html_link=None,
            status="confirmed",
            start="2026-12-21",
            end="2026-12-24",
            created=datetime(2026, 11, 13, 12, 0, tzinfo=MADRID),
        )
    )
    set_calendar_connector(connector)

    output = run_create(
        title="Vacaciones",
        start="2026-12-21T00:00:00+01:00",
        end="2026-12-24T00:00:00+01:00",
        all_day=True,
        idempotency_key="vacaciones-2026",
    )

    assert output.start == "2026-12-21"
    assert output.end == "2026-12-24"
    assert connector.create_calls[0]["all_day"] is True


def test_create_event_rejects_invalid_email_and_key() -> None:
    with pytest.raises(ValidationError):
        CreateEventInput.model_validate(
            {
                "title": "Demo",
                "start": "2026-11-16T10:00:00+01:00",
                "end": "2026-11-16T11:00:00+01:00",
                "attendees": ["no-es-email"],
                "idempotency_key": "demo-2026-11-16",
            }
        )
    with pytest.raises(ValidationError):
        CreateEventInput.model_validate(
            {
                "title": "Demo",
                "start": "2026-11-16T10:00:00+01:00",
                "end": "2026-11-16T11:00:00+01:00",
                "idempotency_key": "short",
            }
        )


def test_create_event_rejects_invalid_recurrence() -> None:
    with pytest.raises(ValidationError):
        CreateEventInput.model_validate(
            {
                "title": "Demo",
                "start": "2026-11-16T10:00:00+01:00",
                "end": "2026-11-16T11:00:00+01:00",
                "recurrence_rrule": "FREQ=WEEKLY",
                "idempotency_key": "demo-2026-11-16",
            }
        )


def test_create_event_without_connector_fails_closed() -> None:
    with pytest.raises(ToolError) as error:
        run_create(
            title="Demo",
            start="2026-11-16T10:00:00+01:00",
            end="2026-11-16T11:00:00+01:00",
            idempotency_key="demo-2026-11-16",
        )

    assert error.value.code == "connector_not_connected"
