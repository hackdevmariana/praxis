from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.clock import MADRID, today
from app.context import ToolContext
from app.money import quantize_money
from app.providers.savings import SavingsEntryRecord, get_savings_repository
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.procurement.savings_ledger.schemas import (
    CategoryTotal,
    SavingsCategory,
    SavingsEntry,
    SavingsLedgerInput,
    SavingsLedgerOutput,
    SavingsStatus,
)


def _default_period() -> tuple[date, date]:
    current_year = today(MADRID).year
    return date(current_year, 1, 1), date(current_year, 12, 31)


def _aggregate(records: list[SavingsEntryRecord]) -> tuple[list[SavingsEntry], list[CategoryTotal]]:
    entries: list[SavingsEntry] = []
    grouped: dict[SavingsCategory, list[SavingsEntry]] = defaultdict(list)
    for record in records:
        savings = quantize_money(record.baseline_cost - record.actual_cost)
        entry = SavingsEntry(
            id=record.id,
            date=record.entry_date,
            category=SavingsCategory(record.category),
            supplier=record.supplier,
            description=record.description,
            baseline_cost=quantize_money(record.baseline_cost),
            actual_cost=quantize_money(record.actual_cost),
            savings=savings,
            annualized_savings=quantize_money(record.annualized_savings),
            status=record.status,
        )
        entries.append(entry)
        grouped[entry.category].append(entry)

    entries.sort(key=lambda entry: (entry.date, entry.savings), reverse=True)
    totals = [
        CategoryTotal(
            category=category,
            savings=quantize_money(sum((entry.savings for entry in values), Decimal("0.00"))),
            annualized_savings=quantize_money(
                sum((entry.annualized_savings for entry in values), Decimal("0.00"))
            ),
            count=len(values),
        )
        for category, values in grouped.items()
    ]
    totals.sort(key=lambda total: (total.savings, total.category.value), reverse=True)
    return entries, totals


@tool(
    name="procurement.savings_ledger",
    version="0.1.0",
    title="Registro de ahorros del tenant",
    permissions=["procurement.read"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Agrega el registro de ahorros del tenant por periodo, categoría y estado. "
        "Los importes se leen de la base de datos protegida por RLS; esta tool solo "
        "consulta y no da de alta registros."
    ),
)
async def savings_ledger(
    params: SavingsLedgerInput, ctx: ToolContext
) -> ToolResult[SavingsLedgerOutput]:
    period_start, period_end = params.period_start, params.period_end
    if period_start is None or period_end is None:
        period_start, period_end = _default_period()

    records = await get_savings_repository(ctx).list_for_company(
        company_id=ctx.company_id or "",
        period_start=period_start,
        period_end=period_end,
    )
    if params.category is not None:
        records = [record for record in records if record.category == params.category.value]
    if params.status is not SavingsStatus.all:
        records = [record for record in records if record.status == params.status.value]

    entries, totals = _aggregate(records)
    output = SavingsLedgerOutput(
        period_start=period_start,
        period_end=period_end,
        entries=entries,
        total_savings=quantize_money(sum((entry.savings for entry in entries), Decimal("0.00"))),
        total_annualized=quantize_money(
            sum((entry.annualized_savings for entry in entries), Decimal("0.00"))
        ),
        by_category=totals,
        count=len(entries),
        currency=params.currency,
    )
    return tool_result(
        output,
        metadata_extra={
            "source": "database",
            "source_type": "database",
            "result_type": "aggregation",
            "is_estimated": False,
            "currency": params.currency,
        },
        summary=f"{output.count} ahorros por {output.total_savings} {params.currency}.",
    )
