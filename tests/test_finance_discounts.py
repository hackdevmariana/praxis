import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.tools.finance.discounts.schemas import DiscountsInput, DiscountsOutput
from app.tools.finance.discounts.tool import calculate_discounts

CTX = ToolContext(request_id="test")


def run(**kwargs: object) -> DiscountsOutput:
    result = asyncio.run(calculate_discounts(DiscountsInput.model_validate(kwargs), CTX))
    return result.data


def test_cascading_discounts_are_not_additive() -> None:
    output = run(amount="1000", discounts=["10", "5"])

    assert output.original_amount == Decimal("1000.00")
    assert output.final_amount == Decimal("855.00")
    assert output.discount_amount == Decimal("145.00")
    assert output.effective_discount_pct == Decimal("14.50")


def test_reverse_recovers_original_amount() -> None:
    output = run(amount="855", discounts=["10", "5"], operation="reverse")

    assert output.original_amount == Decimal("1000.00")
    assert output.final_amount == Decimal("855.00")
    assert output.discount_amount == Decimal("145.00")
    assert output.effective_discount_pct == Decimal("14.50")


def test_single_discount_and_reverse() -> None:
    applied = run(amount="100", discounts=["20"])
    reversed_ = run(amount="100", discounts=["20"], operation="reverse")

    assert applied.final_amount == Decimal("80.00")
    assert applied.effective_discount_pct == Decimal("20.00")
    assert reversed_.original_amount == Decimal("125.00")
    assert reversed_.discount_amount == Decimal("25.00")


def test_full_discount_yields_zero() -> None:
    output = run(amount="50", discounts=["100"])

    assert output.final_amount == Decimal("0.00")
    assert output.discount_amount == Decimal("50.00")
    assert output.effective_discount_pct == Decimal("100.00")


def test_reverse_with_full_discount_is_tool_error() -> None:
    with pytest.raises(ToolError) as error:
        run(amount="50", discounts=["100"], operation="reverse")

    assert error.value.code == ErrorCode.INVALID_PARAMS


def test_zero_amount() -> None:
    output = run(amount="0", discounts=["10"])

    assert output.final_amount == Decimal("0.00")
    assert output.effective_discount_pct == Decimal("0.00")


def test_invalid_discounts_are_schema_errors() -> None:
    with pytest.raises(ValidationError):
        DiscountsInput.model_validate({"amount": "100", "discounts": []})

    with pytest.raises(ValidationError):
        DiscountsInput.model_validate({"amount": "100", "discounts": ["101"]})

    with pytest.raises(ValidationError):
        DiscountsInput.model_validate({"amount": "-1", "discounts": ["10"]})
