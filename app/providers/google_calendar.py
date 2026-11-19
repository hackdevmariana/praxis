"""Injectable Google Calendar connector contract."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.context import ToolContext
from app.errors import ErrorCode, ToolError


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


@dataclass(frozen=True, slots=True)
class PersistedEvent:
    company_id: str
    event_id: str
    calendar_id: str
    title: str
    start: str
    end: str
    html_link: str | None
    status: str
    idempotency_key: str | None


class CalendarTokenProvider(Protocol):
    async def get_access_token(self, ctx: ToolContext) -> str: ...


class EventRepository(Protocol):
    async def save(self, event: PersistedEvent) -> None: ...


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
            ErrorCode.CONNECTOR_NOT_CONNECTED,
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
            ErrorCode.CONNECTOR_NOT_CONNECTED,
            "El usuario no tiene Google Calendar conectado.",
        )


class NoopEventRepository:
    async def save(self, event: PersistedEvent) -> None:
        return None


_connector: CalendarConnector = UnconfiguredCalendarConnector()
_event_repository: EventRepository = NoopEventRepository()


def get_calendar_connector(ctx: ToolContext) -> CalendarConnector:
    return _connector


def set_calendar_connector(connector: CalendarConnector | None) -> None:
    global _connector
    _connector = connector or UnconfiguredCalendarConnector()


def get_event_repository(ctx: ToolContext) -> EventRepository:
    return _event_repository


def set_event_repository(repository: EventRepository | None) -> None:
    global _event_repository
    _event_repository = repository or NoopEventRepository()
