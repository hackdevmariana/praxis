import asyncio
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.db.models import (
    CompanyRow,
    DataSourceRow,
    IdempotencyRecordRow,
    TenantProfileRow,
)
from app.db.rls import company_session

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
            session.add(
                IdempotencyRecordRow(
                    key="key-a",
                    company_id=company_a,
                    input_hash="hash-a",
                    result={"value": "a"},
                    expires_at="2026-12-01T00:00:00+00:00",
                )
            )
            await session.commit()

        async with company_session(engine, company_b) as session:
            session.add(CompanyRow(id=company_b, name="Polígono B"))
            session.add(TenantProfileRow(company_id=company_b, catalog_key="poligono"))
            await session.commit()

        async with company_session(engine, company_a) as session:
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

        async with company_session(engine, company_a) as session:
            session.add(TenantProfileRow(company_id=company_b, catalog_key="hotel"))
            with pytest.raises(SQLAlchemyError):
                await session.commit()

    asyncio.run(scenario())
    asyncio.run(engine.dispose())
