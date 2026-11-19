from datetime import date, datetime, time, timedelta
from typing import cast
from uuid import uuid4

from pydantic import BaseModel

from app.clock import MADRID, now
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.idempotency import deduplicated_value, get_idempotency_store, scoped_key
from app.providers.alerts import (
    AlertEventRecord,
    AlertMessage,
    AlertRuleRecord,
    get_alert_notifier,
    get_alert_rule_repository,
)
from app.providers.contracts import get_contract_repository
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.alerts.contract_renewal.schemas import (
    Channel,
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
        "idempotency_key. Regla y disparos se persisten; el notificador configurado "
        "envía los avisos cuando llegan a su fecha."
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

    equivalent_key = scoped_key(
        "alerts.contract_renewal",
        company_id,
        "contract",
        params.contract_id,
        params.renewal_date.isoformat(),
    )
    record = await get_idempotency_store().get(equivalent_key)
    stored_value = record.value if record is not None else None
    if isinstance(stored_value, ToolResult):
        stored = cast(ToolResult[BaseModel], cast(object, stored_value))
        if isinstance(stored.data, ContractRenewalOutput):
            return cast(
                ToolResult[ContractRenewalOutput],
                deduplicated_value(stored),
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

    rule_id = uuid4()
    events = tuple(
        AlertEventRecord(
            id=uuid4(),
            company_id=company_id,
            alert_rule_id=rule_id,
            days_before=entry.days_before,
            trigger_at=entry.trigger_at,
            channel=entry.channel.value,
            status=entry.status,
        )
        for entry in entries
    )
    await get_alert_rule_repository(ctx).save(
        AlertRuleRecord(
            id=rule_id,
            company_id=company_id,
            contract_id=params.contract_id,
            renewal_date=params.renewal_date,
            channel=params.channel.value,
            next_trigger_at=entries[0].trigger_at if entries else None,
            idempotency_key=params.idempotency_key,
        ),
        events,
    )

    notifications_sent = 0
    if params.channel == Channel.email and params.recipient is not None:
        notifier = get_alert_notifier(ctx)
        for entry in entries:
            if entry.trigger_at > moment:
                continue
            await notifier.send(
                AlertMessage(
                    company_id=company_id,
                    contract_id=params.contract_id,
                    recipient=str(params.recipient),
                    subject=f"Renovación de contrato en {entry.days_before} días",
                    body=(
                        f"El contrato {params.contract_id} se renueva el "
                        f"{params.renewal_date.isoformat()}."
                    ),
                    trigger_at=entry.trigger_at,
                )
            )
            notifications_sent += 1

    output = ContractRenewalOutput(
        alert_rule_id=str(rule_id),
        renewal_date=params.renewal_date,
        next_trigger_at=entries[0].trigger_at if entries else None,
        schedule=entries,
        deduplicated=False,
    )

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
            "alert_rule_id": str(rule_id),
            "notifications_sent": notifications_sent,
        },
        idempotency_aliases=(equivalent_key,),
    )
