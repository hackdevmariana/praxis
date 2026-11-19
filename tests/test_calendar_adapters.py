import asyncio
import json
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.context import ToolContext
from app.errors import ToolError
from app.providers.google_calendar import (
    PersistedEvent,
    set_calendar_connector,
    set_event_repository,
)
from app.providers.google_calendar_adapters import (
    GoogleCalendarConnector,
    RefreshTokenProvider,
    StaticTokenProvider,
)
from app.tools.calendar.create_event.schemas import CreateEventInput
from app.tools.calendar.create_event.tool import create_event

TOKEN_URL = "https://oauth2.googleapis.com/token"
BASE_URL = "https://www.googleapis.com/calendar/v3"
CTX = ToolContext(request_id="test", user_id="user-1", company_id="company-1", confirmed=True)


class RecordingEventRepository:
    def __init__(self) -> None:
        self.events: list[PersistedEvent] = []

    async def save(self, event: PersistedEvent) -> None:
        self.events.append(event)


@respx.mock
def test_refresh_token_provider_caches_access_token() -> None:
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "access-1"})
    )
    provider = RefreshTokenProvider("client", "secret", "refresh")

    assert asyncio.run(provider.get_access_token(CTX)) == "access-1"
    assert asyncio.run(provider.get_access_token(CTX)) == "access-1"
    assert route.call_count == 1
    body = parse_qs(route.calls.last.request.content.decode())
    assert body["grant_type"] == ["refresh_token"]


@respx.mock
def test_list_events_maps_google_payload() -> None:
    respx.get(f"{BASE_URL}/calendars/primary/events").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "evt-1",
                        "summary": "Cita",
                        "start": {"dateTime": "2026-11-20T10:00:00+01:00"},
                        "end": {"dateTime": "2026-11-20T11:00:00+01:00"},
                        "location": "Madrid",
                        "attendees": [{"email": "ana@example.com"}],
                        "status": "confirmed",
                        "htmlLink": "https://calendar.google.com/event/evt-1",
                    }
                ],
                "nextPageToken": "next",
            },
        )
    )
    connector = GoogleCalendarConnector(StaticTokenProvider("token"))

    page = asyncio.run(
        connector.list_events(
            calendar_id="primary",
            start=datetime(2026, 11, 1, tzinfo=UTC),
            end=datetime(2026, 12, 1, tzinfo=UTC),
            max_results=25,
        )
    )

    assert len(page.events) == 1
    assert page.next_page_token == "next"
    assert page.events[0].title == "Cita"
    assert page.events[0].attendees == ("ana@example.com",)
    assert page.events[0].is_all_day is False


@respx.mock
def test_create_event_posts_payload_and_persists_mirror() -> None:
    route = respx.post(f"{BASE_URL}/calendars/primary/events").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "evt-2",
                "htmlLink": "https://calendar.google.com/event/evt-2",
                "status": "confirmed",
                "start": {"dateTime": "2026-11-20T10:00:00+01:00"},
                "end": {"dateTime": "2026-11-20T11:00:00+01:00"},
                "created": "2026-11-19T09:00:00Z",
            },
        )
    )
    repository = RecordingEventRepository()
    set_calendar_connector(GoogleCalendarConnector(StaticTokenProvider("token")))
    set_event_repository(repository)

    result = asyncio.run(
        create_event(
            CreateEventInput.model_validate(
                {
                    "title": "Reunión",
                    "start": "2026-11-20T10:00:00+01:00",
                    "end": "2026-11-20T11:00:00+01:00",
                    "attendees": ["ana@example.com"],
                    "recurrence_rrule": "RRULE:FREQ=WEEKLY;COUNT=4",
                    "idempotency_key": "reunion-2026-11-20",
                }
            ),
            CTX,
        )
    )

    body = json.loads(route.calls.last.request.content)
    assert body["summary"] == "Reunión"
    assert body["recurrence"] == ["RRULE:FREQ=WEEKLY;COUNT=4"]
    assert body["attendees"] == [{"email": "ana@example.com"}]
    assert result.data.event_id == "evt-2"
    assert result.data.deduplicated is False
    assert len(repository.events) == 1
    assert repository.events[0].event_id == "evt-2"
    assert repository.events[0].company_id == "company-1"


@respx.mock
def test_google_auth_error_is_mapped() -> None:
    respx.get(f"{BASE_URL}/calendars/primary/events").mock(return_value=httpx.Response(401))
    connector = GoogleCalendarConnector(StaticTokenProvider("token"))

    with pytest.raises(ToolError) as error:
        asyncio.run(
            connector.list_events(
                calendar_id="primary",
                start=datetime(2026, 11, 1, tzinfo=UTC),
                end=datetime(2026, 12, 1, tzinfo=UTC),
                max_results=10,
            )
        )

    assert error.value.code == "connector_auth_expired"
