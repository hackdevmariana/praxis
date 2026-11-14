from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.clock import today as current_date
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.datetime.calc.schemas import DateCalcInput, DateCalcOutput, Operation

_WEEKDAYS = (
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ToolError(ErrorCode.INVALID_PARAMS, f"Zona horaria inválida: {name}") from error


@tool(
    name="datetime.calc",
    version="1.0.0",
    title="Calcular fechas",
    permissions=["datetime.read"],
    data_classification="public",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Opera con fechas: hoy, sumar o restar días, diferencia en días naturales, "
        "día de la semana y semana ISO. No cuenta días laborables; para eso usar "
        "datetime.business_days. No usar para horas ni zonas horarias de eventos."
    ),
)
async def date_calc(params: DateCalcInput, ctx: ToolContext) -> ToolResult[DateCalcOutput]:
    timezone = _timezone(params.timezone)

    if params.operation is Operation.today:
        return tool_result(DateCalcOutput(operation=Operation.today, date=current_date(timezone)))

    assert params.date is not None

    if params.operation is Operation.add_days:
        assert params.days is not None
        return tool_result(
            DateCalcOutput(
                operation=Operation.add_days,
                date=params.date + timedelta(days=params.days),
            )
        )

    if params.operation is Operation.diff_days:
        assert params.date_b is not None
        return tool_result(
            DateCalcOutput(
                operation=Operation.diff_days,
                days_diff=(params.date_b - params.date).days,
            )
        )

    if params.operation is Operation.weekday:
        weekday = params.date.isoweekday()
        return tool_result(
            DateCalcOutput(
                operation=Operation.weekday,
                weekday=weekday,
                weekday_name=_WEEKDAYS[weekday - 1],
            )
        )

    calendar = params.date.isocalendar()
    day_of_year = (params.date - date(params.date.year, 1, 1)).days + 1
    return tool_result(
        DateCalcOutput(
            operation=Operation.week_info,
            iso_week=calendar.week,
            iso_year=calendar.year,
            quarter=(params.date.month - 1) // 3 + 1,
            semester=1 if params.date.month <= 6 else 2,
            day_of_year=day_of_year,
        )
    )
