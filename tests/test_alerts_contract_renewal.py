import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import pytest
import time_machine
from pydantic import ValidationError

from app.clock import MADRID
from app.context import ToolContext
from app.errors import ToolError
from app.providers.contracts import ContractRecord, set_contract_repository
from app.tools.alerts.contract_renewal.schemas import (
    ContractRenewalInput,
    ContractRenewalOutput,
)
from app.tools.alerts.contract_renewal.tool import schedule_contract_renewal

CTX = ToolContext(request_id="test", company_id="company-1", confirmed=True)
CONTRACT_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_CONTRACT_ID = UUID("33333333-3333-4333-8333-333333333333")
INACTIVE_CONTRACT_ID = UUID("55555555-5555-4555-8555-555555555555")
FIXED_NOW = datetime(2026, 11, 13, 10, 0, tzinfo=MADRID)


class FakeContractRepository:
    def __init__(self, contracts: dict[UUID, ContractRecord]) -> None:
        self.contracts = contracts

    async def get(self, *, company_id: str, contract_id: UUID) -> ContractRecord | None:
        contract = self.contracts.get(contract_id)
        if contract is None or contract.company_id != company_id:
            return None
        return contract


def install_repository(*contracts: ContractRecord) -> None:
    set_contract_repository(
        FakeContractRepository({contract.id: contract for contract in contracts})
    )


def run_result(**kwargs: object) -> ContractRenewalOutput:
    return asyncio.run(
        schedule_contract_renewal(ContractRenewalInput.model_validate(kwargs), CTX)
    ).data


def test_future_renewal_golden() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="company-1"))

    with time_machine.travel(FIXED_NOW, tick=False):
        output = run_result(
            contract_id=str(CONTRACT_ID),
            renewal_date="2027-03-31",
            notice_days=[60, 30, 15],
            channel="none",
            idempotency_key="renovacion-contrato-111-2027",
        )

    assert str(UUID(output.alert_rule_id)) == output.alert_rule_id
    assert output.next_trigger_at == datetime(2027, 1, 30, 9, 0, tzinfo=MADRID)
    assert [entry.days_before for entry in output.schedule] == [60, 30, 15]
    assert output.schedule[0].trigger_at == datetime(2027, 1, 30, 9, 0, tzinfo=MADRID)
    assert output.schedule[2].trigger_at == datetime(2027, 3, 16, 9, 0, tzinfo=MADRID)
    assert all(entry.status == "pending" for entry in output.schedule)
    assert output.deduplicated is False


def test_past_notice_days_are_skipped_with_warning() -> None:
    install_repository(ContractRecord(id=OTHER_CONTRACT_ID, company_id="company-1"))

    with time_machine.travel(FIXED_NOW, tick=False):
        result = asyncio.run(
            schedule_contract_renewal(
                ContractRenewalInput.model_validate(
                    {
                        "contract_id": str(OTHER_CONTRACT_ID),
                        "renewal_date": "2026-12-15",
                        "notice_days": [60, 30, 15],
                        "channel": "email",
                        "idempotency_key": "renovacion-contrato-333-2026",
                    }
                ),
                CTX,
            )
        )

    assert [entry.days_before for entry in result.data.schedule] == [30, 15]
    assert result.data.next_trigger_at == datetime(2026, 11, 15, 9, 0, tzinfo=MADRID)
    assert result.data.schedule[0].channel == "email"
    assert result.warnings == ["notice_days_in_past"]


def test_renewal_today_has_no_future_triggers() -> None:
    install_repository(ContractRecord(id=INACTIVE_CONTRACT_ID, company_id="company-1"))

    with time_machine.travel(FIXED_NOW, tick=False):
        result = asyncio.run(
            schedule_contract_renewal(
                ContractRenewalInput.model_validate(
                    {
                        "contract_id": str(INACTIVE_CONTRACT_ID),
                        "renewal_date": "2026-11-13",
                        "notice_days": [60, 30, 15],
                        "channel": "none",
                        "idempotency_key": "renovacion-contrato-555-2026",
                    }
                ),
                CTX,
            )
        )

    assert result.data.schedule == []
    assert result.data.next_trigger_at is None
    assert result.warnings == ["notice_days_in_past", "no_future_triggers"]


def test_dst_offset_is_applied_per_trigger() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="company-1"))

    with time_machine.travel(FIXED_NOW, tick=False):
        output = run_result(
            contract_id=str(CONTRACT_ID),
            renewal_date="2027-04-15",
            notice_days=[30, 15],
            idempotency_key="renovacion-dst-2027",
        )

    offsets = [entry.trigger_at.utcoffset() for entry in output.schedule]
    assert offsets == [timedelta(hours=1), timedelta(hours=2)]


def test_past_renewal_date_is_invalid() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="company-1"))

    with (
        time_machine.travel(FIXED_NOW, tick=False),
        pytest.raises(ToolError) as error,
    ):
        run_result(
            contract_id=str(CONTRACT_ID),
            renewal_date="2026-11-12",
            idempotency_key="renovacion-pasada-2026",
        )

    assert error.value.code == "invalid_params"


def test_contract_not_found() -> None:
    set_contract_repository(FakeContractRepository({}))

    with (
        time_machine.travel(FIXED_NOW, tick=False),
        pytest.raises(ToolError) as error,
    ):
        run_result(
            contract_id=str(CONTRACT_ID),
            renewal_date="2027-03-31",
            idempotency_key="renovacion-inexistente-2027",
        )

    assert error.value.code == "contract_not_found"


def test_contract_from_other_company_is_not_visible() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="otra"))

    with (
        time_machine.travel(FIXED_NOW, tick=False),
        pytest.raises(ToolError) as error,
    ):
        run_result(
            contract_id=str(CONTRACT_ID),
            renewal_date="2027-03-31",
            idempotency_key="renovacion-otra-empresa-2027",
        )

    assert error.value.code == "contract_not_found"


def test_inactive_contract_still_schedules_with_warning() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="company-1", is_active=False))

    with time_machine.travel(FIXED_NOW, tick=False):
        result = asyncio.run(
            schedule_contract_renewal(
                ContractRenewalInput.model_validate(
                    {
                        "contract_id": str(CONTRACT_ID),
                        "renewal_date": "2027-03-31",
                        "idempotency_key": "renovacion-inactivo-2027",
                    }
                ),
                CTX,
            )
        )

    assert len(result.data.schedule) == 3
    assert result.warnings == ["contract_not_active"]


def test_confirmation_is_required() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="company-1"))
    unconfirmed = ToolContext(request_id="test", company_id="company-1")

    with (
        time_machine.travel(FIXED_NOW, tick=False),
        pytest.raises(ToolError) as error,
    ):
        asyncio.run(
            schedule_contract_renewal(
                ContractRenewalInput.model_validate(
                    {
                        "contract_id": str(CONTRACT_ID),
                        "renewal_date": "2027-03-31",
                        "idempotency_key": "renovacion-sin-confirmar-2027",
                    }
                ),
                unconfirmed,
            )
        )

    assert error.value.code == "confirmation_required"


def test_same_idempotency_key_is_deduplicated() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="company-1"))
    payload = {
        "contract_id": str(CONTRACT_ID),
        "renewal_date": "2027-03-31",
        "idempotency_key": "renovacion-dedupe-2027",
    }

    with time_machine.travel(FIXED_NOW, tick=False):
        first = run_result(**payload)
        second = run_result(**payload)

    assert first.deduplicated is False
    assert second.deduplicated is True
    assert second.alert_rule_id == first.alert_rule_id


def test_equivalent_rule_is_deduplicated_across_keys() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id="company-1"))

    with time_machine.travel(FIXED_NOW, tick=False):
        first = run_result(
            contract_id=str(CONTRACT_ID),
            renewal_date="2027-03-31",
            idempotency_key="renovacion-clave-a-2027",
        )
        second = run_result(
            contract_id=str(CONTRACT_ID),
            renewal_date="2027-03-31",
            idempotency_key="renovacion-clave-b-2027",
        )

    assert second.deduplicated is True
    assert second.alert_rule_id == first.alert_rule_id


def test_duplicate_or_out_of_range_notice_days_are_invalid() -> None:
    with pytest.raises(ValidationError):
        ContractRenewalInput.model_validate(
            {
                "contract_id": str(CONTRACT_ID),
                "renewal_date": "2027-03-31",
                "notice_days": [30, 30],
                "idempotency_key": "renovacion-duplicada-2027",
            }
        )
    with pytest.raises(ValidationError):
        ContractRenewalInput.model_validate(
            {
                "contract_id": str(CONTRACT_ID),
                "renewal_date": "2027-03-31",
                "notice_days": [366],
                "idempotency_key": "renovacion-fuera-rango-2027",
            }
        )
