from app.business_days import count_business_days, holiday_metadata
from app.context import ToolContext
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.datetime.business_days.schemas import (
    BusinessDaysInput,
    BusinessDaysOutput,
    HolidayApplied,
)


@tool(
    name="datetime.business_days",
    version="1.0.0",
    title="Contar días hábiles",
    permissions=["datetime.read"],
    data_classification="public",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Cuenta días hábiles entre dos fechas excluyendo fines de semana y festivos "
        "nacionales, autonómicos y locales. El inicio es inclusivo y el fin exclusivo "
        "salvo include_end=true. No usar para días naturales; para eso usar datetime.calc."
    ),
)
async def business_days(
    params: BusinessDaysInput, ctx: ToolContext
) -> ToolResult[BusinessDaysOutput]:
    result = count_business_days(
        params.start,
        params.end,
        include_end=params.include_end,
        community=params.community,
        municipality_code=params.municipality_code,
    )
    metadata = holiday_metadata(result)
    metadata["source"] = "seeder:holidays"
    metadata["source_type"] = "database"

    return tool_result(
        BusinessDaysOutput(
            business_days=result.business_days,
            calendar_days=result.calendar_days,
            holidays_applied=[
                HolidayApplied(date=holiday.date, name=holiday.name, scope=holiday.scope)
                for holiday in result.holidays
            ],
        ),
        warnings=result.warnings,
        metadata_extra=metadata,
    )
