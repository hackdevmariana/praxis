import asyncio
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.finance.cashflow_13w.schemas import Cashflow13wInput, Cashflow13wOutput
from app.tools.finance.cashflow_13w.tool import cashflow_13w

CTX = ToolContext(request_id="test")


def weekly(value: str) -> list[str]:
    return [value] * 13


def run_result(**kwargs: object) -> ToolResult[Cashflow13wOutput]:
    return asyncio.run(cashflow_13w(Cashflow13wInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> Cashflow13wOutput:
    return run_result(**kwargs).data


def test_golden_case() -> None:
    result = run_result(
        opening_balance="10000",
        weekly_inflows=weekly("5000"),
        weekly_outflows=weekly("6000"),
        start_date="2026-11-16",
    )
    output = result.data

    assert len(output.weeks) == 13
    assert [week.closing_balance for week in output.weeks] == [
        Decimal("9000.00"),
        Decimal("8000.00"),
        Decimal("7000.00"),
        Decimal("6000.00"),
        Decimal("5000.00"),
        Decimal("4000.00"),
        Decimal("3000.00"),
        Decimal("2000.00"),
        Decimal("1000.00"),
        Decimal("0.00"),
        Decimal("-1000.00"),
        Decimal("-2000.00"),
        Decimal("-3000.00"),
    ]
    assert output.weeks[0].week_start == date(2026, 11, 16)
    assert output.weeks[9].week_start == date(2027, 1, 18)
    assert output.weeks[-1].week_start == date(2027, 2, 8)
    assert output.end_balance == Decimal("-3000.00")
    assert output.min_balance == Decimal("-3000.00")
    assert output.min_week == 13
    assert output.weeks_with_negative_balance == 3
    assert result.warnings == ["negative_balance_risk"]


def test_positive_flow_has_no_warning() -> None:
    result = run_result(
        opening_balance="0",
        weekly_inflows=weekly("7000"),
        weekly_outflows=weekly("5000"),
    )
    output = result.data

    assert output.end_balance == Decimal("26000.00")
    assert output.min_balance == Decimal("2000.00")
    assert output.min_week == 1
    assert output.weeks_with_negative_balance == 0
    assert result.warnings == []
    assert all(week.week_start is None for week in output.weeks)


def test_negative_opening_balance() -> None:
    output = run(
        opening_balance="-5000",
        weekly_inflows=weekly("0"),
        weekly_outflows=weekly("0"),
    )

    assert output.end_balance == Decimal("-5000.00")
    assert output.min_week == 1
    assert output.weeks_with_negative_balance == 13


def test_zero_closing_balance_is_not_negative() -> None:
    output = run(
        opening_balance="0",
        weekly_inflows=weekly("1000"),
        weekly_outflows=weekly("1000"),
    )

    assert output.end_balance == Decimal("0.00")
    assert output.weeks_with_negative_balance == 0


def test_metadata() -> None:
    result = run_result(
        opening_balance="10000",
        weekly_inflows=weekly("5000"),
        weekly_outflows=weekly("6000"),
    )

    assert result.metadata_extra == {
        "source": "user_input",
        "source_type": "user_input",
        "result_type": "forecast",
        "is_estimated": True,
        "confidence": 0.7,
        "currency": "EUR",
        "legal_disclaimer_required": True,
    }


def test_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        Cashflow13wInput.model_validate(
            {
                "opening_balance": "10000",
                "weekly_inflows": ["5000"] * 12,
                "weekly_outflows": weekly("6000"),
            }
        )

    with pytest.raises(ValidationError):
        Cashflow13wInput.model_validate(
            {
                "opening_balance": "10000",
                "weekly_inflows": weekly("5000"),
                "weekly_outflows": ["-100", *["6000"] * 12],
            }
        )
