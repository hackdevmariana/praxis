import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ToolError
from app.result import ToolResult
from app.tools.finance.break_even.schemas import BreakEvenInput, BreakEvenOutput
from app.tools.finance.break_even.tool import calculate_break_even

CTX = ToolContext(request_id="test")

BASE = {
    "fixed_costs": "100000",
    "variable_cost_per_unit": "20",
    "price_per_unit": "50",
    "target_profit": "30000",
    "expected_units": 5000,
}


def run_result(**kwargs: object) -> ToolResult[BreakEvenOutput]:
    return asyncio.run(calculate_break_even(BreakEvenInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> BreakEvenOutput:
    return run_result(**kwargs).data


def test_golden_case() -> None:
    output = run(**BASE)

    assert output.contribution_margin_per_unit == Decimal("30.00")
    assert output.contribution_margin_pct == Decimal("60.00")
    assert output.break_even_units == 3334
    assert output.break_even_revenue == Decimal("166666.67")
    assert output.units_for_target_profit == 4334
    assert output.margin_of_safety_units == 1666
    assert output.margin_of_safety_pct == Decimal("33.32")
    assert output.currency == "EUR"


def test_without_target_or_expected_units() -> None:
    output = run(fixed_costs="100000", variable_cost_per_unit="20", price_per_unit="50")

    assert output.units_for_target_profit == 3334
    assert output.margin_of_safety_units is None
    assert output.margin_of_safety_pct is None


def test_zero_expected_units_leaves_margin_of_safety_undefined() -> None:
    output = run(
        fixed_costs="100000",
        variable_cost_per_unit="20",
        price_per_unit="50",
        expected_units=0,
    )

    assert output.margin_of_safety_units is None
    assert output.margin_of_safety_pct is None


def test_contribution_margin_equal_to_zero_is_invalid() -> None:
    with pytest.raises(ToolError, match="margen de contribución") as error:
        run(fixed_costs="10000", variable_cost_per_unit="20", price_per_unit="20")

    assert error.value.code == "invalid_params"


def test_contribution_margin_below_zero_is_invalid() -> None:
    with pytest.raises(ToolError, match="margen de contribución"):
        run(fixed_costs="10000", variable_cost_per_unit="20", price_per_unit="15")


def test_metadata() -> None:
    result = run_result(**BASE)

    assert result.metadata_extra == {
        "source": "user_input",
        "source_type": "user_input",
        "result_type": "calculation",
        "is_estimated": True,
        "confidence": 0.85,
        "currency": "EUR",
        "legal_disclaimer_required": True,
    }


def test_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        BreakEvenInput.model_validate({**BASE, "fixed_costs": "-1"})

    with pytest.raises(ValidationError):
        BreakEvenInput.model_validate({**BASE, "price_per_unit": "0"})

    with pytest.raises(ValidationError):
        BreakEvenInput.model_validate({**BASE, "expected_units": -1})
