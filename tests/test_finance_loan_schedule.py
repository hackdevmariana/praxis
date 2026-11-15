import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.tools.finance.loan_schedule.schemas import LoanInput, LoanOutput
from app.tools.finance.loan_schedule.tool import loan_schedule

CTX = ToolContext(request_id="test")


def run(**kwargs: object) -> LoanOutput:
    result = asyncio.run(loan_schedule(LoanInput.model_validate(kwargs), CTX))
    return result.data


def test_french_schedule_golden() -> None:
    output = run(principal="10000", annual_rate="6", term_months=12)

    assert output.monthly_payment == Decimal("860.66")
    assert output.first_payment == Decimal("860.66")
    assert output.last_payment == Decimal("860.70")
    assert output.total_interest == Decimal("327.96")
    assert output.total_paid == Decimal("10327.96")
    assert len(output.schedule) == 12
    assert output.schedule[0].interest == Decimal("50.00")
    assert output.schedule[0].principal == Decimal("810.66")
    assert output.schedule[-1].balance == Decimal("0.00")


def test_italian_schedule_golden() -> None:
    output = run(principal="10000", annual_rate="6", term_months=12, type="italian")

    assert output.monthly_payment is None
    assert output.first_payment == Decimal("883.33")
    assert output.last_payment == Decimal("837.54")
    assert output.total_interest == Decimal("325.00")
    assert output.total_paid == Decimal("10325.00")
    assert output.schedule[0].principal == Decimal("833.33")
    assert output.schedule[-1].balance == Decimal("0.00")


def test_zero_rate_french() -> None:
    output = run(principal="15000", annual_rate="0", term_months=12)

    assert output.monthly_payment == Decimal("1250.00")
    assert output.total_interest == Decimal("0.00")
    assert output.total_paid == Decimal("15000.00")
    assert all(item.interest == Decimal("0.00") for item in output.schedule)


def test_annual_rate_defaults_to_zero() -> None:
    output = run(principal="1200", term_months=12)

    assert output.annual_rate == Decimal("0")
    assert output.monthly_payment == Decimal("100.00")
    assert output.total_interest == Decimal("0.00")


def test_zero_rate_italian() -> None:
    output = run(principal="1000", annual_rate="0", term_months=4, type="italian")

    assert output.total_interest == Decimal("0.00")
    assert output.total_paid == Decimal("1000.00")
    assert output.first_payment == Decimal("250.00")
    assert output.last_payment == Decimal("250.00")


def test_schedule_balances_sum_to_principal() -> None:
    output = run(principal="999.99", annual_rate="4.75", term_months=36)

    assert output.schedule[-1].balance == Decimal("0.00")
    assert sum(item.principal for item in output.schedule) == Decimal("999.99")
    assert output.total_paid == output.principal + output.total_interest


def test_invalid_loan_inputs() -> None:
    with pytest.raises(ValidationError):
        LoanInput.model_validate({"principal": "0", "annual_rate": "5", "term_months": 12})

    with pytest.raises(ValidationError):
        LoanInput.model_validate({"principal": "1000", "annual_rate": "5", "term_months": 0})
