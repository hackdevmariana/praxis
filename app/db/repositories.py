from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import AlertEventRow, AlertRuleRow, CalendarEventRow, ContractRow
from app.db.rls import company_session
from app.errors import ErrorCode, ToolError
from app.providers.alerts import AlertEventRecord, AlertRuleRecord
from app.providers.contracts import ContractRecord
from app.providers.google_calendar import PersistedEvent


def _company(company_id: str) -> UUID:
    try:
        return UUID(company_id)
    except ValueError as error:
        raise ToolError(
            ErrorCode.INVALID_PARAMS,
            "company_id debe ser un UUID válido para repositorios SQL.",
        ) from error


class SqlContractRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def get(self, *, company_id: str, contract_id: UUID) -> ContractRecord | None:
        company = _company(company_id)
        async with company_session(self.engine, company) as session:
            row = await session.get(ContractRow, contract_id)
            if row is None:
                return None
            return ContractRecord(
                id=row.id,
                company_id=company_id,
                is_active=row.is_active,
            )


class SqlEventRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def save(self, event: PersistedEvent) -> None:
        company = _company(event.company_id)
        async with company_session(self.engine, company) as session:
            existing = await session.scalar(
                select(CalendarEventRow).where(CalendarEventRow.event_id == event.event_id)
            )
            if existing is not None:
                return
            session.add(
                CalendarEventRow(
                    company_id=company,
                    event_id=event.event_id,
                    calendar_id=event.calendar_id,
                    title=event.title,
                    starts_at=event.start,
                    ends_at=event.end,
                    html_link=event.html_link,
                    status=event.status,
                    idempotency_key=event.idempotency_key,
                )
            )
            await session.commit()


class SqlAlertRuleRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def save(self, rule: AlertRuleRecord, events: tuple[AlertEventRecord, ...]) -> None:
        company = _company(rule.company_id)
        async with company_session(self.engine, company) as session:
            session.add(
                AlertRuleRow(
                    id=rule.id,
                    company_id=company,
                    contract_id=rule.contract_id,
                    renewal_date=rule.renewal_date,
                    channel=rule.channel,
                    next_trigger_at=rule.next_trigger_at,
                    idempotency_key=rule.idempotency_key,
                )
            )
            await session.flush()
            session.add_all(
                [
                    AlertEventRow(
                        id=event.id,
                        company_id=company,
                        alert_rule_id=rule.id,
                        days_before=event.days_before,
                        trigger_at=event.trigger_at,
                        channel=event.channel,
                        status=event.status,
                    )
                    for event in events
                ]
            )
            await session.commit()
