from datetime import timedelta

from app.clock import MADRID, today
from app.context import ToolContext
from app.providers.renewals import get_renewal_repository
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.procurement.renewal_calendar.schemas import (
    RenewalCalendarInput,
    RenewalCalendarOutput,
    RenewalItem,
)


@tool(
    name="procurement.renewal_calendar",
    version="0.1.0",
    title="Calendario de renovaciones de contratos",
    permissions=["procurement.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Lista las renovaciones de contratos del tenant en un horizonte de hasta "
        "365 días, con el estado de aviso según los días de preaviso registrados. "
        "Solo consulta datos de la base de datos protegida por RLS."
    ),
)
async def renewal_calendar(
    params: RenewalCalendarInput, ctx: ToolContext
) -> ToolResult[RenewalCalendarOutput]:
    reference_date = params.reference_date or today(MADRID)
    horizon_end = reference_date + timedelta(days=params.horizon_days)
    records = await get_renewal_repository(ctx).list_for_company(company_id=ctx.company_id or "")

    renewals: list[RenewalItem] = []
    for record in records:
        if params.category is not None and record.category != params.category:
            continue
        if record.renewal_date > horizon_end:
            continue
        days_remaining = (record.renewal_date - reference_date).days
        if days_remaining < 0 and not params.include_expired:
            continue

        if days_remaining < 0:
            status = "expired"
        elif record.notice_days and days_remaining <= max(record.notice_days):
            status = "notice_due"
        else:
            status = "upcoming"

        renewals.append(
            RenewalItem(
                contract_id=record.contract_id,
                supplier=record.supplier,
                category=record.category,
                renewal_date=record.renewal_date,
                days_remaining=days_remaining,
                notice_days=list(record.notice_days),
                status=status,
                estimated_annual_cost=record.estimated_annual_cost,
            )
        )

    renewals.sort(key=lambda item: (item.renewal_date, item.supplier))
    next_renewal = min(
        (item.renewal_date for item in renewals if item.days_remaining >= 0),
        default=None,
    )
    output = RenewalCalendarOutput(
        reference_date=reference_date,
        horizon_end=horizon_end,
        count=len(renewals),
        notice_due_count=sum(item.status == "notice_due" for item in renewals),
        next_renewal=next_renewal,
        renewals=renewals,
        currency=params.currency,
    )
    return tool_result(
        output,
        metadata_extra={
            "source": "database",
            "source_type": "database",
            "result_type": "list",
            "is_estimated": False,
            "currency": params.currency,
            "timezone": "Europe/Madrid",
        },
        summary=(
            f"{output.count} renovaciones en el horizonte, {output.notice_due_count} con aviso."
        ),
    )
