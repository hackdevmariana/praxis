from calendar import monthrange
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.business_days import count_business_days, holiday_metadata, holiday_source_detail
from app.clock import MADRID
from app.clock import today as current_date
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.holidays import load_dataset
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.calendar.deadline_remaining.schemas import (
    DeadlineInput,
    DeadlineOutput,
    Period,
)
from app.tools.datetime.business_days.schemas import HolidayApplied


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ToolError(ErrorCode.INVALID_PARAMS, f"Zona horaria inválida: {name}") from error


def _limits(period: Period, reference: date) -> tuple[date, date]:
    if period is Period.month:
        start = date(reference.year, reference.month, 1)
        last_day = monthrange(reference.year, reference.month)[1]
        return start, date(reference.year, reference.month, last_day)

    if period is Period.quarter:
        first_month = (reference.month - 1) // 3 * 3 + 1
        last_month = first_month + 2
        return (
            date(reference.year, first_month, 1),
            date(reference.year, last_month, monthrange(reference.year, last_month)[1]),
        )

    return date(reference.year, 1, 1), date(reference.year, 12, 31)


@tool(
    name="calendar.deadline_remaining",
    version="1.0.0",
    title="Días restantes hasta el cierre",
    permissions=["datetime.read"],
    data_classification="public",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Calcula los días naturales y hábiles que quedan hasta el cierre del mes, "
        "trimestre o año. Descuenta festivos nacionales, autonómicos y locales. "
        "No usar para plazos fiscales ni para fechas de eventos de calendario."
    ),
)
async def deadline_remaining(params: DeadlineInput, ctx: ToolContext) -> ToolResult[DeadlineOutput]:
    timezone = _timezone(params.timezone)
    reference = params.reference_date or current_date(timezone)
    period_start, deadline = _limits(params.period, reference)
    days_remaining = max(0, (deadline - reference).days)

    if reference < deadline:
        result = count_business_days(
            reference + timedelta(days=1),
            deadline,
            include_end=True,
            community=params.community,
            municipality_code=params.municipality_code,
        )
        business_days = result.business_days
        holidays = result.holidays
        warnings = result.warnings
        metadata = holiday_metadata(result)
        metadata["source"] = "deterministic+seeder:holidays"
        metadata["source_type"] = "deterministic"
    else:
        dataset = load_dataset()
        business_days = 0
        holidays = ()
        warnings = ()
        metadata = {
            "source": "deterministic+seeder:holidays",
            "source_type": "deterministic",
            "valid_until": datetime.combine(dataset.valid_until, time.min, tzinfo=MADRID),
            "holiday_dataset_version": dataset.version,
            "source_detail": holiday_source_detail(),
        }

    return tool_result(
        DeadlineOutput(
            period=params.period,
            period_start=period_start,
            deadline=deadline,
            days_remaining=days_remaining,
            business_days_remaining=business_days,
            holidays_applied=[
                HolidayApplied(date=holiday.date, name=holiday.name, scope=holiday.scope)
                for holiday in holidays
            ],
        ),
        warnings=warnings,
        metadata_extra=metadata,
    )
