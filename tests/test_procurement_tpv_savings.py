import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.procurement.tpv_savings.schemas import (
    TpvSavingsInput,
    TpvSavingsOutput,
)
from app.tools.procurement.tpv_savings.tool import calculate_tpv_savings

CTX = ToolContext(request_id="test")


def run_result(**kwargs: object) -> ToolResult[TpvSavingsOutput]:
    return asyncio.run(calculate_tpv_savings(TpvSavingsInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> TpvSavingsOutput:
    return run_result(**kwargs).data


def test_typical_savings_golden() -> None:
    output = run(
        annual_card_turnover="500000",
        current_rate_pct="1.5",
        new_rate_pct="0.9",
        average_ticket="25",
    )

    assert output.current_cost == Decimal("7500.00")
    assert output.new_cost == Decimal("4500.00")
    assert output.annual_savings == Decimal("3000.00")
    assert output.monthly_savings == Decimal("250.00")
    assert output.savings_pct == Decimal("40.00")
    assert output.savings_per_ticket == Decimal("0.15")
    assert output.currency == "EUR"


def test_more_expensive_offer_has_negative_savings() -> None:
    output = run(
        annual_card_turnover="100000",
        current_rate_pct="1.0",
        new_rate_pct="1.2",
    )

    assert output.current_cost == Decimal("1000.00")
    assert output.new_cost == Decimal("1200.00")
    assert output.annual_savings == Decimal("-200.00")
    assert output.monthly_savings == Decimal("-16.67")
    assert output.savings_pct == Decimal("-20.00")
    assert output.savings_per_ticket is None


def test_equal_rates_have_zero_savings() -> None:
    output = run(
        annual_card_turnover="100000",
        current_rate_pct="1.0",
        new_rate_pct="1.0",
    )

    assert output.annual_savings == Decimal("0.00")
    assert output.savings_pct == Decimal("0.00")


def test_zero_current_cost_warns_undefined_percentage() -> None:
    result = run_result(
        annual_card_turnover="100000",
        current_rate_pct="0",
        new_rate_pct="1",
    )

    assert result.data.current_cost == Decimal("0.00")
    assert result.data.new_cost == Decimal("1000.00")
    assert result.data.annual_savings == Decimal("-1000.00")
    assert result.data.monthly_savings == Decimal("-83.33")
    assert result.data.savings_pct is None
    assert result.warnings == ["undefined_savings_pct"]


def test_zero_turnover_has_no_per_ticket_savings() -> None:
    result = run_result(
        annual_card_turnover="0",
        current_rate_pct="1.5",
        new_rate_pct="0.9",
        average_ticket="25",
    )

    assert result.data.annual_savings == Decimal("0.00")
    assert result.data.savings_pct is None
    assert result.data.savings_per_ticket is None
    assert result.warnings == ["undefined_savings_pct"]


def test_metadata_marks_estimate_and_legal_disclaimer() -> None:
    result = run_result(
        annual_card_turnover="100000",
        current_rate_pct="1.5",
        new_rate_pct="0.9",
    )

    assert result.metadata_extra["result_type"] == "calculation"
    assert result.metadata_extra["is_estimated"] is True
    assert result.metadata_extra["confidence"] == 0.9
    assert result.metadata_extra["legal_disclaimer_required"] is True


def test_rate_above_100_is_schema_error() -> None:
    with pytest.raises(ValidationError):
        TpvSavingsInput.model_validate(
            {
                "annual_card_turnover": "100000",
                "current_rate_pct": "1.5",
                "new_rate_pct": "101",
            }
        )
