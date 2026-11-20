import asyncio
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.clock import MADRID, today
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.savings import SavingsEntryRecord, set_savings_repository
from app.result import ToolResult
from app.tools.procurement.savings_ledger.schemas import SavingsLedgerInput, SavingsLedgerOutput
from app.tools.procurement.savings_ledger.tool import savings_ledger

COMPANY = "33333333-3333-4333-8333-333333333333"
CTX = ToolContext(request_id="test", company_id=COMPANY, scopes=frozenset({"procurement.read"}))


def entry(
    identifier: str,
    when: str,
    category: str,
    baseline: str,
    actual: str,
    annualized: str,
    status: str,
) -> SavingsEntryRecord:
    return SavingsEntryRecord(
        id=identifier,
        company_id=COMPANY,
        entry_date=date.fromisoformat(when),
        category=category,
        supplier="Proveedor",
        description=f"Registro {identifier}",
        baseline_cost=Decimal(baseline),
        actual_cost=Decimal(actual),
        annualized_savings=Decimal(annualized),
        status=status,
    )


class FakeSavingsRepository:
    def __init__(self, entries: tuple[SavingsEntryRecord, ...] = ()) -> None:
        self.entries = entries
        self.seen: list[tuple[date, date]] = []

    async def list_for_company(
        self, *, company_id: str, period_start: date, period_end: date
    ) -> list[SavingsEntryRecord]:
        self.seen.append((period_start, period_end))
        return [
            record
            for record in self.entries
            if record.company_id == company_id and period_start <= record.entry_date <= period_end
        ]


def install(*entries: SavingsEntryRecord) -> FakeSavingsRepository:
    repository = FakeSavingsRepository(entries)
    set_savings_repository(repository)
    return repository


def run_result(**kwargs: object) -> ToolResult[SavingsLedgerOutput]:
    return asyncio.run(savings_ledger(SavingsLedgerInput.model_validate(kwargs), CTX))


GOLDEN_ENTRIES = (
    entry("sv_001", "2026-02-15", "tpv", "7500", "4500", "3000", "realized"),
    entry("sv_002", "2026-06-01", "energy", "4200", "3000", "1400", "realized"),
    entry("sv_003", "2026-11-10", "supplies", "12000", "11200", "800", "projected"),
)


def test_golden_case() -> None:
    install(*GOLDEN_ENTRIES)
    result = run_result(period_start="2026-01-01", period_end="2026-12-31")
    output = result.data

    assert output.period_start == date(2026, 1, 1)
    assert output.period_end == date(2026, 12, 31)
    assert output.count == 3
    assert output.total_savings == Decimal("5000.00")
    assert output.total_annualized == Decimal("5200.00")
    assert output.currency == "EUR"
    assert [item.id for item in output.entries] == ["sv_003", "sv_002", "sv_001"]
    assert output.entries[0].savings == Decimal("800.00")
    assert output.entries[0].status == "projected"
    assert [(total.category.value, total.savings) for total in output.by_category] == [
        ("tpv", Decimal("3000.00")),
        ("energy", Decimal("1200.00")),
        ("supplies", Decimal("800.00")),
    ]
    assert output.by_category[0].annualized_savings == Decimal("3000.00")
    assert output.by_category[0].count == 1


def test_filter_by_category_and_status() -> None:
    install(*GOLDEN_ENTRIES)
    energy = run_result(period_start="2026-01-01", period_end="2026-12-31", category="energy").data
    assert [item.id for item in energy.entries] == ["sv_002"]
    assert energy.total_annualized == Decimal("1400.00")

    realized = run_result(
        period_start="2026-01-01", period_end="2026-12-31", status="realized"
    ).data
    assert [item.id for item in realized.entries] == ["sv_002", "sv_001"]
    assert realized.total_savings == Decimal("4200.00")


def test_empty_period_is_not_an_error() -> None:
    repository = install()
    output = run_result(period_start="2027-01-01", period_end="2027-12-31").data

    assert output.count == 0
    assert output.total_savings == Decimal("0.00")
    assert output.total_annualized == Decimal("0.00")
    assert output.entries == []
    assert output.by_category == []
    assert repository.seen == [(date(2027, 1, 1), date(2027, 12, 31))]


def test_negative_savings_reduce_totals_and_ties_use_amount() -> None:
    install(
        entry("sv_a", "2026-03-01", "other", "100", "150", "-50", "realized"),
        entry("sv_b", "2026-03-01", "other", "100", "90", "10", "realized"),
    )
    output = run_result(period_start="2026-01-01", period_end="2026-12-31").data

    assert [item.id for item in output.entries] == ["sv_b", "sv_a"]
    assert output.total_savings == Decimal("-40.00")
    assert output.total_annualized == Decimal("-40.00")
    assert output.by_category[0].savings == Decimal("-40.00")


def test_default_period_is_current_year() -> None:
    repository = install()
    output = run_result().data
    current_year = today(MADRID).year

    assert output.period_start == date(current_year, 1, 1)
    assert output.period_end == date(current_year, 12, 31)
    assert repository.seen == [(date(current_year, 1, 1), date(current_year, 12, 31))]


def test_metadata_is_database_aggregation() -> None:
    install(*GOLDEN_ENTRIES)
    result = run_result(period_start="2026-01-01", period_end="2026-12-31")

    assert result.metadata_extra["source"] == "database"
    assert result.metadata_extra["source_type"] == "database"
    assert result.metadata_extra["result_type"] == "aggregation"
    assert result.metadata_extra["is_estimated"] is False
    assert result.warnings == []


def test_unconfigured_repository_fails_closed() -> None:
    with pytest.raises(ToolError) as excinfo:
        run_result(period_start="2026-01-01", period_end="2026-12-31")

    assert excinfo.value.code == ErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.parametrize(
    "payload",
    [
        {"period_start": "2026-12-31", "period_end": "2026-01-01"},
        {"period_start": "2026-01-01"},
        {"period_end": "2026-12-31"},
        {"status": "unknown"},
        {"category": "unknown"},
    ],
)
def test_invalid_params_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SavingsLedgerInput.model_validate(payload)
