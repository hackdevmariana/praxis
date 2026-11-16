from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.cache import TTLCache
from app.providers.google_calendar import (
    CalendarEventRecord,
    CalendarPage,
    get_calendar_connector,
)
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.calendar.list_events.schemas import (
    CalendarEventOut,
    ListEventsInput,
    ListEventsOutput,
)

_CACHE: TTLCache[CalendarPage] = TTLCache()


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ToolError(ErrorCode.INVALID_PARAMS, f"Zona horaria inválida: {name}") from error


def _as_aware(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value


def _event_bound(value: str, timezone: ZoneInfo) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Google Calendar devolvió una fecha de evento inválida.",
        ) from error
    return _as_aware(parsed, timezone)


def _overlaps(
    record: CalendarEventRecord,
    start: datetime,
    end: datetime,
    timezone: ZoneInfo,
) -> bool:
    return _event_bound(record.start, timezone) < end and _event_bound(record.end, timezone) > start


@tool(
    name="calendar.list_events",
    version="1.0.0",
    title="Listar eventos de agenda",
    permissions=["calendar.read"],
    data_classification="personal",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    open_world=True,
    mcp_description=(
        "Lista los eventos del calendario del usuario autenticado que solapan "
        "un rango. Expande recurrentes, respeta eventos de día completo y no "
        "acepta user_id como parámetro. Requiere un conector de Google Calendar."
    ),
)
async def list_events(params: ListEventsInput, ctx: ToolContext) -> ToolResult[ListEventsOutput]:
    timezone = _timezone(params.timezone)
    start = _as_aware(params.start, timezone)
    end = _as_aware(params.end, timezone)

    cache_key = "|".join(
        (
            ctx.user_id or "",
            ctx.company_id or "",
            params.calendar_id,
            start.isoformat(),
            end.isoformat(),
            str(params.max_results),
        )
    )
    cached = _CACHE.get(cache_key)
    if cached is None:
        connector = get_calendar_connector(ctx)
        page = await connector.list_events(
            calendar_id=params.calendar_id,
            start=start,
            end=end,
            max_results=params.max_results,
        )
        cached = _CACHE.set(cache_key, page, timedelta(seconds=60))
    page = cached.value

    selected = [record for record in page.events if _overlaps(record, start, end, timezone)]
    selected.sort(key=lambda record: _event_bound(record.start, timezone))

    return tool_result(
        ListEventsOutput(
            events=[
                CalendarEventOut(
                    id=record.id,
                    title=record.title,
                    start=record.start,
                    end=record.end,
                    location=record.location,
                    attendees=list(record.attendees),
                    status=record.status,
                    is_all_day=record.is_all_day,
                    html_link=record.html_link,
                )
                for record in selected[: params.max_results]
            ],
            next_page_token=page.next_page_token,
            timezone=params.timezone,
        ),
        metadata_extra={
            "source": "google_calendar",
            "source_type": "connector",
            "valid_until": cached.valid_until,
            "result_type": "list",
            "timezone": params.timezone,
        },
    )
