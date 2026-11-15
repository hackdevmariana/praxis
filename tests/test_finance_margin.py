import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.finance.margin.schemas import MarginInput, MarginOutput
from app.tools.finance.margin.tool import calculate_margin

CTX = ToolContext(request_id="test")


def run_result(**kwargs: object) -> ToolResult[MarginOutput]:
    return asyncio.run(calculate_margin(MarginInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> MarginOutput:
    return run_result(**kwargs).data


def test_cost_and_price() -> None:
    output = run(cost="100", price="150")

    assert output.margin_amount == Decimal("50.00")
    assert output.margin_pct == Decimal("33.33")
    assert output.markup_pct == Decimal("50.00")


def test_cost_and_margin_derives_price() -> None:
    output = run(cost="100", margin_pct="40")

    assert output.price == Decimal("166.67")
    assert output.margin_amount == Decimal("66.67")
    assert output.margin_pct == Decimal("40.00")
    assert output.markup_pct == Decimal("66.67")


def test_price_and_margin_derives_cost() -> None:
    output = run(price="100", margin_pct="30")

    assert output.cost == Decimal("70.00")
    assert output.margin_amount == Decimal("30.00")
    assert output.markup_pct == Decimal("42.86")


def test_price_below_cost_is_negative() -> None:
    output = run(cost="100", price="80")

    assert output.margin_amount == Decimal("-20.00")
    assert output.margin_pct == Decimal("-25.00")
    assert output.markup_pct == Decimal("-20.00")


def test_zero_cost_warns_markup_undefined() -> None:
    result = run_result(cost="0", price="50")

    assert result.data.margin_amount == Decimal("50.00")
    assert result.data.margin_pct == Decimal("100.00")
    assert result.data.markup_pct is None
    assert result.warnings == ["markup_undefined"]


def test_zero_price_warns_margin_undefined() -> None:
    result = run_result(cost="10", price="0")

    assert result.data.margin_pct is None
    assert result.data.markup_pct == Decimal("-100.00")
    assert result.warnings == ["margin_undefined"]


def test_zero_cost_and_price() -> None:
    result = run_result(cost="0", price="0")

    assert result.data.margin_pct == Decimal("0.00")
    assert result.data.markup_pct == Decimal("0.00")
    assert result.warnings == []


def test_requires_exactly_two_inputs() -> None:
    with pytest.raises(ValidationError, match="exactamente dos"):
        MarginInput.model_validate({"cost": "100"})

    with pytest.raises(ValidationError, match="exactamente dos"):
        MarginInput.model_validate({"cost": "100", "price": "150", "margin_pct": "20"})
