import asyncio
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.clock import MADRID, today
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.renewals import RenewalRecord, set_renewal_repository
from app.result import ToolResult
from app.tools.procurement.renewal_calendar.schemas import (
    RenewalCalendarInput,
    RenewalCalendarOutput,
)
from app.tools.procurement.renewal_calendar.tool import renewal_calendar

CTX = ToolContext(
    request_id="test",
    company_id="33333333-3333-4333-8333-333333333333",
    scopes=frozenset({"procurement.read"}),
)


def record(
    identifier: str,
    supplier: str,
    category: str,
    renewal: str,
    notice: tuple[int, ...],
    cost: str = "1000.00",
) -> RenewalRecord:
    return RenewalRecord(
        contract_id=identifier,
        supplier=supplier,
        category=category,
        renewal_date=date.fromisoformat(renewal),
        notice_days=notice,
        estimated_annual_cost=Decimal(cost),
    )


class FakeRenewalRepository:
    def __init__(self, records: tuple[RenewalRecord, ...] = ()) -> None:
        self.records = records
        self.calls: list[str] = []

    async def list_for_company(self, *, company_id: str) -> list[RenewalRecord]:
        self.calls.append(company_id)
        return list(self.records)


def install(*records: RenewalRecord) -> FakeRenewalRepository:
    repository = FakeRenewalRepository(records)
    set_renewal_repository(repository)
    return repository


def run_result(**kwargs: object) -> ToolResult[RenewalCalendarOutput]:
    return asyncio.run(renewal_calendar(RenewalCalendarInput.model_validate(kwargs), CTX))


GOLDEN_RECORDS = (
    record("c_000", "Mantenimiento Y S.L.", "services", "2026-11-01", (30,), "3600.00"),
    record("c_001", "Suministros García S.L.", "supplies", "2026-12-31", (60, 30, 15), "12000.00"),
    record("c_002", "Eléctrica X", "energy", "2027-01-15", (30,), "8400.00"),
    record("c_003", "Fuera de horizonte", "other", "2027-03-01", (15,)),
)


def test_golden_case() -> None:
    install(*GOLDEN_RECORDS)
    result = run_result(reference_date="2026-11-13", horizon_days=90)
    output = result.data

    assert output.reference_date == date(2026, 11, 13)
    assert output.horizon_end == date(2027, 2, 11)
    assert output.count == 2
    assert output.notice_due_count == 1
    assert output.next_renewal == date(2026, 12, 31)
    assert output.currency == "EUR"
    assert [item.contract_id for item in output.renewals] == ["c_001", "c_002"]
    first, second = output.renewals
    assert first.days_remaining == 48
    assert first.notice_days == [60, 30, 15]
    assert first.status == "notice_due"
    assert first.estimated_annual_cost == Decimal("12000.00")
    assert second.days_remaining == 63
    assert second.status == "upcoming"


def test_expired_contracts_are_excluded_unless_requested() -> None:
    repository = install(*GOLDEN_RECORDS)
    excluded = run_result(reference_date="2026-11-13", horizon_days=90).data
    assert [item.contract_id for item in excluded.renewals] == ["c_001", "c_002"]

    included = run_result(reference_date="2026-11-13", horizon_days=90, include_expired=True).data
    assert [item.contract_id for item in included.renewals] == ["c_000", "c_001", "c_002"]
    assert included.renewals[0].days_remaining == -12
    assert included.renewals[0].status == "expired"
    assert included.next_renewal == date(2026, 12, 31)
    assert repository.calls == [CTX.company_id or "", CTX.company_id or ""]


def test_category_filter_and_no_notice_days() -> None:
    install(*GOLDEN_RECORDS, record("c_004", "Sin aviso", "energy", "2026-12-01", ()))
    output = run_result(reference_date="2026-11-13", horizon_days=60, category="energy").data

    assert [item.contract_id for item in output.renewals] == ["c_004"]
    assert output.renewals[0].status == "upcoming"
    assert output.notice_due_count == 0


def test_ties_are_sorted_by_supplier_and_next_renewal_is_null_when_all_expired() -> None:
    install(
        record("c_b", "Zeta", "other", "2026-12-01", ()),
        record("c_a", "Alfa", "other", "2026-12-01", ()),
    )
    output = run_result(reference_date="2026-11-13", horizon_days=30).data
    assert [item.contract_id for item in output.renewals] == ["c_a", "c_b"]
    assert output.next_renewal == date(2026, 12, 1)

    expired = run_result(reference_date="2026-11-13", horizon_days=30, include_expired=True).data
    install(record("c_x", "Caducado", "other", "2026-11-01", ()))
    only_expired = run_result(
        reference_date="2026-11-13", horizon_days=30, include_expired=True
    ).data
    assert expired.next_renewal == date(2026, 12, 1)
    assert only_expired.next_renewal is None


def test_empty_horizon_is_not_an_error() -> None:
    install(*GOLDEN_RECORDS)
    output = run_result(reference_date="2026-11-13", horizon_days=1).data

    assert output.count == 0
    assert output.renewals == []
    assert output.next_renewal is None
    assert output.notice_due_count == 0


def test_default_reference_date_is_today_in_madrid() -> None:
    install(
        record(
            "c_001",
            "Suministros",
            "supplies",
            (today(MADRID) + timedelta(days=10)).isoformat(),
            (15,),
        )
    )
    output = run_result().data

    assert output.reference_date == today(MADRID)
    assert output.count == 1


def test_metadata_is_database_list() -> None:
    install()
    result = run_result(reference_date="2026-11-13")

    assert result.metadata_extra["source"] == "database"
    assert result.metadata_extra["result_type"] == "list"
    assert result.metadata_extra["is_estimated"] is False
    assert result.metadata_extra["timezone"] == "Europe/Madrid"
    assert result.warnings == []


def test_unconfigured_repository_fails_closed() -> None:
    with pytest.raises(ToolError) as excinfo:
        run_result(reference_date="2026-11-13")

    assert excinfo.value.code == ErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.parametrize("horizon_days", [0, 366, -1])
def test_invalid_horizon_is_rejected(horizon_days: int) -> None:
    with pytest.raises(ValidationError):
        RenewalCalendarInput.model_validate({"horizon_days": horizon_days})
