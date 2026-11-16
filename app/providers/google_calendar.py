"""Injectable Google Calendar connector contract."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.context import ToolContext
from app.errors import ToolError


@dataclass(frozen=True, slots=True)
class CalendarEventRecord:
    id: str
    title: str
    start: str
    end: str
    location: str | None
    attendees: tuple[str, ...]
    status: str
    is_all_day: bool
    html_link: str | None


@dataclass(frozen=True, slots=True)
class CalendarPage:
    events: tuple[CalendarEventRecord, ...]
    next_page_token: str | None = None


@dataclass(frozen=True, slots=True)
class CreatedEventRecord:
    event_id: str
    html_link: str | None
    status: str
    start: str
    end: str
    created: datetime


class CalendarConnector(Protocol):
    async def list_events(
        self,
        *,
        calendar_id: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> CalendarPage: ...

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
    ) -> CreatedEventRecord: ...


class UnconfiguredCalendarConnector:
    """Fail closed until an OAuth-backed connector is installed."""

    async def list_events(
        self,
        *,
        calendar_id: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> CalendarPage:
        raise ToolError(
            "connector_not_connected",
            "El usuario no tiene Google Calendar conectado.",
        )

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
        raise ToolError(
            "connector_not_connected",
            "El usuario no tiene Google Calendar conectado.",
        )


_connector: CalendarConnector = UnconfiguredCalendarConnector()


def get_calendar_connector(ctx: ToolContext) -> CalendarConnector:
    return _connector


def set_calendar_connector(connector: CalendarConnector | None) -> None:
    global _connector
    _connector = connector or UnconfiguredCalendarConnector()
