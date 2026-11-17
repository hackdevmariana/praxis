from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.google_calendar import get_calendar_connector
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.calendar.create_event.schemas import (
    CreateEventInput,
    CreateEventOutput,
)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ToolError(ErrorCode.INVALID_PARAMS, f"Zona horaria inválida: {name}") from error


@tool(
    name="calendar.create_event",
    version="1.0.0",
    title="Crear evento de agenda",
    permissions=["calendar.write"],
    data_classification="personal",
    read_only=False,
    idempotent=True,
    requires_confirmation=True,
    open_world=True,
    mcp_description=(
        "Crea un evento en el calendario del usuario autenticado. Exige "
        "confirmación humana e idempotency_key. En eventos de día completo, end "
        "es exclusivo. Requiere un conector de Google Calendar con permiso de "
        "escritura."
    ),
)
async def create_event(params: CreateEventInput, ctx: ToolContext) -> ToolResult[CreateEventOutput]:
    if not ctx.confirmed:
        raise ToolError(
            ErrorCode.CONFIRMATION_REQUIRED,
            "calendar.create_event requiere confirmación humana.",
        )

    timezone = _timezone(params.timezone)
    connector = get_calendar_connector(ctx)
    record = await connector.create_event(
        calendar_id=params.calendar_id,
        title=params.title,
        start=params.start,
        end=params.end,
        description=params.description,
        location=params.location,
        attendees=list(params.attendees),
        all_day=params.all_day,
        timezone=timezone.key,
        send_notifications=params.send_notifications,
        recurrence_rrule=params.recurrence_rrule,
    )

    output = CreateEventOutput(
        event_id=record.event_id,
        html_link=record.html_link,
        status=record.status,
        start=record.start,
        end=record.end,
        created=record.created,
        deduplicated=False,
    )

    return tool_result(
        output,
        metadata_extra={
            "source": "google_calendar",
            "source_type": "connector",
            "result_type": "mutation",
            "timezone": params.timezone,
            "idempotency_key": params.idempotency_key,
            "effect": "created",
        },
    )
