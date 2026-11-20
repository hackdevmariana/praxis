"""Idempotent seed for the three demo tenants and global data sources."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.engine import create_db_engine
from app.db.models import CompanyRow, DataSourceRow, SavingsEntryRow, TenantProfileRow
from app.db.rls import set_company_context

SEED_VERSION = "2026-11-20"

COMPANIES: tuple[tuple[UUID, str, str, UUID, str], ...] = (
    (
        UUID("11111111-1111-4111-8111-111111111111"),
        "Hotel Sol",
        "hotel",
        UUID("a1111111-1111-4111-8111-111111111111"),
        "hotel",
    ),
    (
        UUID("22222222-2222-4222-8222-222222222222"),
        "Polígono Industrial",
        "poligono",
        UUID("a2222222-2222-4222-8222-222222222222"),
        "poligono",
    ),
    (
        UUID("33333333-3333-4333-8333-333333333333"),
        "Asociación Empresarial",
        "asociacion",
        UUID("a3333333-3333-4333-8333-333333333333"),
        "asociacion",
    ),
)

DATA_SOURCES: tuple[tuple[UUID, str, str], ...] = (
    (UUID("44444444-4444-4444-8444-444444444444"), "dataset:holidays-es", "dataset"),
    (UUID("55555555-5555-4555-8555-555555555555"), "dataset:vat-rates-es", "dataset"),
    (UUID("66666666-6666-4666-8666-666666666666"), "dataset:municipios-es", "dataset"),
    (UUID("77777777-7777-4777-8777-777777777777"), "dataset:cnae-es", "dataset"),
)


@dataclass(frozen=True, slots=True)
class _SavingsSeed:
    id: str
    company_id: UUID
    entry_date: date
    category: str
    supplier: str | None
    description: str
    baseline_cost: Decimal
    actual_cost: Decimal
    annualized_savings: Decimal
    status: str


SAVINGS_ENTRIES: tuple[_SavingsSeed, ...] = (
    _SavingsSeed(
        "sv_001",
        UUID("33333333-3333-4333-8333-333333333333"),
        date(2026, 2, 15),
        "tpv",
        "TPV Y",
        "Cambio de comisión TPV",
        Decimal("7500.00"),
        Decimal("4500.00"),
        Decimal("3000.00"),
        "realized",
    ),
    _SavingsSeed(
        "sv_002",
        UUID("33333333-3333-4333-8333-333333333333"),
        date(2026, 6, 1),
        "energy",
        "Eléctrica X",
        "Cambio de tarifa",
        Decimal("4200.00"),
        Decimal("3000.00"),
        Decimal("1400.00"),
        "realized",
    ),
    _SavingsSeed(
        "sv_003",
        UUID("33333333-3333-4333-8333-333333333333"),
        date(2026, 11, 10),
        "supplies",
        "Molinos S.A.",
        "Renegociación de harina",
        Decimal("12000.00"),
        Decimal("11200.00"),
        Decimal("800.00"),
        "projected",
    ),
)


def _audit_metadata() -> dict[str, str]:
    return {
        "created_by": "seeder",
        "source": "scripts/seed_demo.py",
        "seeder_version": SEED_VERSION,
    }


async def seed(engine: AsyncEngine) -> None:
    """Insert or refresh demo rows using fixed identifiers."""
    async with AsyncSession(engine) as session:
        for company_id, name, catalog_key, profile_id, profile_name in COMPANIES:
            await set_company_context(session, company_id)
            company = await session.get(CompanyRow, company_id)
            if company is None:
                session.add(CompanyRow(id=company_id, name=name))
            else:
                company.name = name

            profile = await session.get(TenantProfileRow, profile_id)
            if profile is None:
                session.add(
                    TenantProfileRow(
                        id=profile_id,
                        company_id=company_id,
                        catalog_key=catalog_key,
                        is_active=True,
                        config={"name": profile_name, **_audit_metadata()},
                    )
                )
            else:
                profile.company_id = company_id
                profile.catalog_key = catalog_key
                profile.is_active = True
                profile.config = {"name": profile_name, **_audit_metadata()}

            for entry in SAVINGS_ENTRIES:
                if entry.company_id != company_id or await session.get(SavingsEntryRow, entry.id):
                    continue
                session.add(
                    SavingsEntryRow(
                        id=entry.id,
                        company_id=company_id,
                        entry_date=entry.entry_date,
                        category=entry.category,
                        supplier=entry.supplier,
                        description=entry.description,
                        baseline_cost=entry.baseline_cost,
                        actual_cost=entry.actual_cost,
                        annualized_savings=entry.annualized_savings,
                        status=entry.status,
                    )
                )

        for source_id, name, source_type in DATA_SOURCES:
            source = await session.get(DataSourceRow, source_id)
            if source is None:
                session.add(
                    DataSourceRow(
                        id=source_id,
                        name=name,
                        source_type=source_type,
                        base_url=None,
                        is_active=True,
                    )
                )
            else:
                source.name = name
                source.source_type = source_type
                source.is_active = True

        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed PRAXIS demo tenants")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    args = parser.parse_args()

    engine = create_db_engine(args.database_url)
    if engine is None:
        parser.error("DATABASE_URL o --database-url es obligatoria")
    try:
        asyncio.run(seed(engine))
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    main()
