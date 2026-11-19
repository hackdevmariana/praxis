from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote

import httpx

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.google_calendar import (
    CalendarConnector,
    CalendarEventRecord,
    CalendarPage,
    CalendarTokenProvider,
    CreatedEventRecord,
)


@dataclass(slots=True)
class RefreshTokenProvider:
    """OAuth refresh-token flow with in-process access-token caching."""

    client_id: str
    client_secret: str
    refresh_token: str
    token_url: str = "https://oauth2.googleapis.com/token"
    _access_token: str | None = field(default=None, init=False, repr=False)

    async def get_access_token(self, ctx: ToolContext) -> str:
        if self._access_token is not None:
            return self._access_token
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
            )
        _raise_for_status(response, " renovar el token de Google")
        payload = cast(dict[str, Any], response.json())
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise ToolError(
                ErrorCode.CONNECTOR_AUTH_EXPIRED,
                "Google no devolvió un access_token válido.",
            )
        self._access_token = token
        return token


@dataclass(slots=True)
class StaticTokenProvider:
    """Token provisionado por el despliegue; útil para cuentas de servicio."""

    access_token: str

    async def get_access_token(self, ctx: ToolContext) -> str:
        return self.access_token


class GoogleCalendarConnector(CalendarConnector):
    """CalendarConnector backed by the Google Calendar REST API."""

    def __init__(
        self,
        token_provider: CalendarTokenProvider,
        *,
        base_url: str = "https://www.googleapis.com/calendar/v3",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._tokens = token_provider
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def list_events(
        self,
        *,
        calendar_id: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> CalendarPage:
        payload = await self._request(
            "GET",
            f"/calendars/{quote(calendar_id, safe='')}/events",
            params={
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "maxResults": str(max_results),
            },
        )
        items = payload.get("items", [])
        return CalendarPage(
            events=tuple(_event_from_json(cast(dict[str, Any], item)) for item in items),
            next_page_token=payload.get("nextPageToken"),
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
        body: dict[str, Any] = {
            "summary": title,
            "description": description or "",
            "location": location or "",
            "attendees": [{"email": email} for email in attendees],
            "sendNotifications": send_notifications,
        }
        if all_day:
            body["start"] = {"date": start.date().isoformat()}
            body["end"] = {"date": end.date().isoformat()}
        else:
            body["start"] = {"dateTime": start.isoformat(), "timeZone": timezone}
            body["end"] = {"dateTime": end.isoformat(), "timeZone": timezone}
        if recurrence_rrule:
            body["recurrence"] = [recurrence_rrule]

        payload = await self._request(
            "POST",
            f"/calendars/{quote(calendar_id, safe='')}/events",
            json=body,
        )
        created_raw = payload.get("created")
        created = (
            datetime.fromisoformat(created_raw)
            if isinstance(created_raw, str)
            else datetime.now(UTC)
        )
        return CreatedEventRecord(
            event_id=str(payload.get("id", "")),
            html_link=payload.get("htmlLink"),
            status=str(payload.get("status", "confirmed")),
            start=_date_value(payload.get("start")),
            end=_date_value(payload.get("end")),
            created=created,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self._tokens.get_access_token(_CONTEXT)
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self._base_url}{path}"
        if self._client is not None:
            response = await self._client.request(
                method, url, params=params, json=json, headers=headers
            )
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(
                    method, url, params=params, json=json, headers=headers
                )
        _raise_for_status(response, " consultar Google Calendar")
        return cast(dict[str, Any], response.json())


_CONTEXT = ToolContext(request_id="google-calendar")


def _raise_for_status(response: httpx.Response, action: str) -> None:
    status = response.status_code
    if 200 <= status < 300:
        return
    if status == 401:
        raise ToolError(ErrorCode.CONNECTOR_AUTH_EXPIRED, f"No se pudo{action}: token caducado.")
    if status == 403:
        raise ToolError(ErrorCode.PERMISSION_DENIED, f"No se pudo{action}: permiso denegado.")
    if status == 429:
        raise ToolError(ErrorCode.RATE_LIMITED, f"No se pudo{action}: demasiadas peticiones.")
    if status >= 500:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            f"No se pudo{action}: servicio no disponible.",
        )
    raise ToolError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        f"No se pudo{action}.",
        details={"status": status},
    )


def _date_value(value: object) -> str:
    if isinstance(value, dict):
        mapping = cast(dict[str, Any], value)
        date_time = mapping.get("dateTime")
        if isinstance(date_time, str):
            return date_time
        date_only = mapping.get("date")
        if isinstance(date_only, str):
            return date_only
    return ""


def _event_from_json(item: dict[str, Any]) -> CalendarEventRecord:
    start = _date_value(item.get("start"))
    raw_attendees = cast(list[Any], item.get("attendees", []))
    emails: list[str] = []
    for attendee in raw_attendees:
        if not isinstance(attendee, dict):
            continue
        email = cast(dict[str, Any], attendee).get("email")
        if isinstance(email, str):
            emails.append(email)
    attendees = tuple(emails)
    return CalendarEventRecord(
        id=str(item.get("id", "")),
        title=str(item.get("summary", "")),
        start=start,
        end=_date_value(item.get("end")),
        location=item.get("location"),
        attendees=attendees,
        status=str(item.get("status", "confirmed")),
        is_all_day="T" not in start,
        html_link=item.get("htmlLink"),
    )
