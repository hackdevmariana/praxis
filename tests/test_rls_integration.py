import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.audit import ExecutionLogRecord, SqlAlchemyExecutionLogStore
from app.context import ToolContext
from app.db.idempotency import SqlAlchemyIdempotencyStore
from app.db.models import (
    AlertEventRow,
    AlertRuleRow,
    CalendarEventRow,
    CompanyRow,
    ContractRow,
    DataSourceRow,
    IdempotencyRecordRow,
    TenantProfileRow,
    ToolActivationRow,
    ToolExecutionLogRow,
)
from app.db.rls import company_session
from app.idempotency import scoped_key
from app.result import ToolResult, tool_result
from app.tenancy import SqlAlchemyToolAccessPolicy
from app.tools.finance.vat.schemas import VatOutput

pytestmark = pytest.mark.integration
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresContainer]:
    try:
        with PostgresContainer(
            "postgres:16-alpine",
            driver="asyncpg",
            username="praxis_admin",
            password="praxis_admin",
            dbname="praxis",
        ) as container:
            yield container
    except Exception as error:
        pytest.skip(f"Docker no disponible para tests de integración: {error}")


def _run_migrations(container: PostgresContainer) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", container.get_connection_url())
        config = Config(str(REPO_ROOT / "alembic.ini"))
        command.upgrade(config, "head")


def _app_database_url(container: PostgresContainer) -> str:
    url = make_url(container.get_connection_url())
    return url.set(username="praxis_app", password="praxis").render_as_string(hide_password=False)


def test_rls_isolates_companies(postgres: PostgresContainer) -> None:
    _run_migrations(postgres)
    engine = create_async_engine(_app_database_url(postgres))
    company_a = uuid4()
    company_b = uuid4()
    contract_id = uuid4()
    alert_rule_id = uuid4()
    event_id = uuid4()

    async def scenario() -> None:
        async with engine.begin() as connection:
            await connection.execute(
                insert(DataSourceRow).values(
                    id=uuid4(),
                    name="Open-Meteo",
                    source_type="weather",
                    base_url="https://api.open-meteo.com",
                )
            )

        async with company_session(engine, company_a) as session:
            session.add(CompanyRow(id=company_a, name="Hotel A"))
            session.add(TenantProfileRow(company_id=company_a, catalog_key="hotel"))
            await session.flush()

            session.add(
                ContractRow(
                    id=contract_id,
                    company_id=company_a,
                    external_ref="CTR-1",
                    title="Contrato A",
                )
            )
            session.add(
                CalendarEventRow(
                    company_id=company_a,
                    event_id="google-1",
                    calendar_id="primary",
                    title="Cita A",
                    starts_at="2026-11-20T10:00:00+01:00",
                    ends_at="2026-11-20T11:00:00+01:00",
                    status="confirmed",
                )
            )
            session.add(
                IdempotencyRecordRow(
                    key="key-a",
                    company_id=company_a,
                    input_hash="hash-a",
                    result={"value": "a"},
                    expires_at=datetime(2026, 12, 1, tzinfo=UTC),
                )
            )
            await session.flush()

            session.add(
                AlertRuleRow(
                    id=alert_rule_id,
                    company_id=company_a,
                    contract_id=contract_id,
                    renewal_date=date(2027, 3, 31),
                    channel="email",
                )
            )
            await session.flush()

            session.add(
                AlertEventRow(
                    id=event_id,
                    company_id=company_a,
                    alert_rule_id=alert_rule_id,
                    days_before=30,
                    trigger_at=datetime(2027, 3, 1, 9, 0, tzinfo=timezone(timedelta(hours=1))),
                    channel="email",
                    status="pending",
                )
            )
            await session.commit()

        async with company_session(engine, company_b) as session:
            session.add(CompanyRow(id=company_b, name="Polígono B"))
            session.add(TenantProfileRow(company_id=company_b, catalog_key="poligono"))
            await session.commit()

        audit_store = SqlAlchemyExecutionLogStore(engine)
        for company_id, tool_name in ((company_a, "finance.vat"), (company_b, "finance.discounts")):
            await audit_store.record(
                ExecutionLogRecord(
                    request_id="req-rls",
                    tool_name=tool_name,
                    tool_version="1.0.0",
                    user_id=None,
                    company_id=str(company_id),
                    channel="mcp",
                    input_hash="hash",
                    execution_time_ms=1,
                    success=True,
                )
            )

        async with company_session(engine, company_a) as session:
            logs = (await session.scalars(select(ToolExecutionLogRow))).all()
            assert [log.tool_name for log in logs] == ["finance.vat"]
            profiles = (await session.scalars(select(TenantProfileRow))).all()
            records = (await session.scalars(select(IdempotencyRecordRow))).all()
            sources = (await session.scalars(select(DataSourceRow))).all()
            assert [profile.company_id for profile in profiles] == [company_a]
            assert [record.key for record in records] == ["key-a"]
            assert [source.name for source in sources] == ["Open-Meteo"]

        async with company_session(engine, company_b) as session:
            profiles = (await session.scalars(select(TenantProfileRow))).all()
            records = (await session.scalars(select(IdempotencyRecordRow))).all()
            assert [profile.company_id for profile in profiles] == [company_b]
            assert records == []
            contracts = (await session.scalars(select(ContractRow))).all()
            events = (await session.scalars(select(CalendarEventRow))).all()
            rules = (await session.scalars(select(AlertRuleRow))).all()
            alerts = (await session.scalars(select(AlertEventRow))).all()
            assert contracts == []
            assert events == []
            assert rules == []
            assert alerts == []

        async with company_session(engine, company_a) as session:
            session.add(TenantProfileRow(company_id=company_b, catalog_key="hotel"))
            with pytest.raises(SQLAlchemyError):
                await session.commit()

    asyncio.run(scenario())
    asyncio.run(engine.dispose())


def test_persistent_stores_respect_tenant_context(postgres: PostgresContainer) -> None:
    _run_migrations(postgres)
    engine = create_async_engine(_app_database_url(postgres))
    company_a = uuid4()
    company_b = uuid4()

    async def scenario() -> None:
        async with company_session(engine, company_a) as session:
            session.add(CompanyRow(id=company_a, name="Hotel persistente"))
            session.add(TenantProfileRow(company_id=company_a, catalog_key="hotel"))
            session.add(
                ToolActivationRow(
                    company_id=company_a,
                    tool_name="finance.vat",
                    version_installed="1.0.0",
                    is_enabled=False,
                    config={},
                    limits_override={},
                )
            )
            session.add(
                ToolActivationRow(
                    company_id=company_a,
                    tool_name="procurement.compare_offers",
                    version_installed="1.0.0",
                    is_enabled=True,
                    config={},
                    limits_override={},
                )
            )
            await session.commit()

        async with company_session(engine, company_b) as session:
            session.add(CompanyRow(id=company_b, name="Polígono persistente"))
            session.add(TenantProfileRow(company_id=company_b, catalog_key="poligono"))
            await session.commit()

        policy = SqlAlchemyToolAccessPolicy(engine)
        allowed_a = await policy.allowed_tools(
            ToolContext(request_id="req", company_id=str(company_a))
        )
        allowed_b = await policy.allowed_tools(
            ToolContext(request_id="req", company_id=str(company_b))
        )
        assert allowed_a is not None and "finance.vat" not in allowed_a
        assert allowed_a is not None and "weather.forecast" in allowed_a
        assert allowed_a is not None and "procurement.compare_offers" not in allowed_a
        assert allowed_b is not None and "finance.vat" in allowed_b
        assert allowed_b is not None and "calendar.create_event" not in allowed_b

        idem = SqlAlchemyIdempotencyStore(engine)
        result = tool_result(
            VatOutput(
                base_amount=Decimal("100.00"),
                vat_rate=Decimal("21"),
                vat_amount=Decimal("21.00"),
                total_amount=Decimal("121.00"),
                currency="EUR",
            ),
            warnings=["warning"],
            metadata_extra={"source": "test"},
            summary="ok",
            idempotency_aliases=("alias",),
        )
        key_a = scoped_key("finance.vat", str(company_a), "hash-a")
        await idem.put(key_a, result, input_hash="hash-a")
        record = await idem.get(key_a)
        assert record is not None and record.input_hash == "hash-a"
        stored = cast(ToolResult[VatOutput], record.value)
        assert isinstance(stored.data, VatOutput)
        assert stored.data == result.data
        assert stored.warnings == ["warning"]
        assert stored.metadata_extra == {"source": "test"}
        assert stored.summary == "ok"
        assert stored.idempotency_aliases == ("alias",)
        assert await idem.get(scoped_key("finance.vat", str(company_b), "hash-a")) is None

        async with company_session(engine, company_a) as session:
            session.add(TenantProfileRow(company_id=company_b, catalog_key="hotel"))
            with pytest.raises(SQLAlchemyError):
                await session.commit()

    asyncio.run(scenario())
    asyncio.run(engine.dispose())
