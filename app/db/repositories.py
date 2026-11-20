from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import (
    AlertEventRow,
    AlertRuleRow,
    CalendarEventRow,
    ContractRow,
    SavingsEntryRow,
)
from app.db.rls import company_session
from app.errors import ErrorCode, ToolError
from app.providers.alerts import AlertEventRecord, AlertRuleRecord
from app.providers.contracts import ContractRecord
from app.providers.google_calendar import PersistedEvent
from app.providers.renewals import RenewalRecord
from app.providers.savings import SavingsEntryRecord


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


class SqlSavingsRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def list_for_company(
        self, *, company_id: str, period_start: date, period_end: date
    ) -> list[SavingsEntryRecord]:
        company = _company(company_id)
        async with company_session(self.engine, company) as session:
            rows = (
                await session.scalars(
                    select(SavingsEntryRow)
                    .where(SavingsEntryRow.entry_date >= period_start)
                    .where(SavingsEntryRow.entry_date <= period_end)
                    .order_by(SavingsEntryRow.entry_date.desc(), SavingsEntryRow.id.desc())
                )
            ).all()
            return [
                SavingsEntryRecord(
                    id=row.id,
                    company_id=company_id,
                    entry_date=row.entry_date,
                    category=row.category,
                    supplier=row.supplier,
                    description=row.description,
                    baseline_cost=row.baseline_cost,
                    actual_cost=row.actual_cost,
                    annualized_savings=row.annualized_savings,
                    status=row.status,
                )
                for row in rows
            ]


class SqlRenewalRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def list_for_company(self, *, company_id: str) -> list[RenewalRecord]:
        company = _company(company_id)
        async with company_session(self.engine, company) as session:
            contracts = (
                await session.scalars(
                    select(ContractRow)
                    .where(ContractRow.is_active.is_(True))
                    .where(ContractRow.renewal_date.is_not(None))
                )
            ).all()
            rules = (await session.scalars(select(AlertRuleRow))).all()
            events = (await session.scalars(select(AlertEventRow))).all()
            days_by_contract: dict[UUID, list[int]] = {}
            rule_ids = {rule.id: rule.contract_id for rule in rules}
            for event in events:
                contract_id = rule_ids.get(event.alert_rule_id)
                if contract_id is not None:
                    days_by_contract.setdefault(contract_id, []).append(event.days_before)
            renewals: list[RenewalRecord] = []
            for row in contracts:
                if row.renewal_date is None:
                    continue
                renewals.append(
                    RenewalRecord(
                        contract_id=str(row.id),
                        supplier=row.supplier or "",
                        category=row.category or "",
                        renewal_date=row.renewal_date,
                        notice_days=tuple(sorted(days_by_contract.get(row.id, []), reverse=True)),
                        estimated_annual_cost=row.estimated_annual_cost,
                    )
                )
            return renewals
