from datetime import date, datetime, time, timedelta
from uuid import uuid4

from app.clock import MADRID, now
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.idempotency import idempotency_store
from app.providers.contracts import get_contract_repository
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.alerts.contract_renewal.schemas import (
    ContractRenewalInput,
    ContractRenewalOutput,
    ScheduleEntry,
)


def _trigger(renewal_date: date, days_before: int) -> datetime:
    return datetime.combine(renewal_date - timedelta(days=days_before), time(9, 0), tzinfo=MADRID)


@tool(
    name="alerts.contract_renewal",
    version="1.0.0",
    title="Programar avisos de renovación",
    permissions=["alerts.write"],
    data_classification="business",
    read_only=False,
    idempotent=True,
    requires_confirmation=True,
    mcp_description=(
        "Programa recordatorios internos a 1-365 días antes de la renovación de "
        "un contrato, a las 09:00 de Europe/Madrid. Exige confirmación humana e "
        "idempotency_key. No envía emails ni WhatsApp en el MVP; solo registra "
        "la regla y sus disparos pendientes."
    ),
)
async def schedule_contract_renewal(
    params: ContractRenewalInput, ctx: ToolContext
) -> ToolResult[ContractRenewalOutput]:
    if not ctx.confirmed:
        raise ToolError(
            ErrorCode.CONFIRMATION_REQUIRED,
            "alerts.contract_renewal requiere confirmación humana.",
        )

    moment = now(MADRID)
    if params.renewal_date < moment.date():
        raise ToolError(
            ErrorCode.INVALID_PARAMS,
            "renewal_date no puede estar en el pasado.",
        )

    company_id = ctx.company_id or ""
    repository = get_contract_repository(ctx)
    contract = await repository.get(company_id=company_id, contract_id=params.contract_id)
    if contract is None:
        raise ToolError(
            "contract_not_found",
            "El contrato no existe en la empresa del usuario.",
            details={"contract_id": str(params.contract_id)},
        )

    key = f"alerts.contract_renewal:{company_id}:{params.idempotency_key}"
    equivalent_key = (
        f"alerts.contract_renewal:contract:{company_id}:"
        f"{params.contract_id}:{params.renewal_date.isoformat()}"
    )
    for lookup in (key, equivalent_key):
        stored = idempotency_store.get(lookup)
        if isinstance(stored, ContractRenewalOutput):
            return tool_result(
                stored.model_copy(update={"deduplicated": True}),
                metadata_extra={
                    "source": "internal",
                    "source_type": "deterministic",
                    "result_type": "mutation",
                    "timezone": MADRID.key,
                    "idempotency_key": params.idempotency_key,
                    "effect": "deduplicated",
                },
            )

    warnings: list[str] = []
    if not contract.is_active:
        warnings.append("contract_not_active")

    entries: list[ScheduleEntry] = []
    skipped: list[int] = []
    for days_before in sorted(params.notice_days, reverse=True):
        trigger_at = _trigger(params.renewal_date, days_before)
        if trigger_at <= moment:
            skipped.append(days_before)
            continue
        entries.append(
            ScheduleEntry(
                days_before=days_before,
                trigger_at=trigger_at,
                channel=params.channel,
                status="pending",
            )
        )

    if skipped:
        warnings.append("notice_days_in_past")
    if not entries:
        warnings.append("no_future_triggers")

    output = ContractRenewalOutput(
        alert_rule_id=str(uuid4()),
        renewal_date=params.renewal_date,
        next_trigger_at=entries[0].trigger_at if entries else None,
        schedule=entries,
        deduplicated=False,
    )
    idempotency_store.put(key, output)
    idempotency_store.put(equivalent_key, output)

    return tool_result(
        output,
        warnings=warnings,
        metadata_extra={
            "source": "internal",
            "source_type": "deterministic",
            "result_type": "mutation",
            "timezone": MADRID.key,
            "idempotency_key": params.idempotency_key,
            "effect": "alert_rule_created",
        },
    )
