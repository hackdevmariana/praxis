import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.finance.ebitda.schemas import EbitdaInput, EbitdaOutput
from app.tools.finance.ebitda.tool import calculate_ebitda

CTX = ToolContext(request_id="test")

BASE = {
    "revenue": "1000000",
    "cogs": "600000",
    "operating_expenses": "250000",
    "depreciation_amortization": "50000",
    "non_recurring_income": "20000",
    "non_recurring_expenses": "10000",
}


def run_result(**kwargs: object) -> ToolResult[EbitdaOutput]:
    return asyncio.run(calculate_ebitda(EbitdaInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> EbitdaOutput:
    return run_result(**kwargs).data


def test_golden_case() -> None:
    output = run(**BASE)

    assert output.ebitda == Decimal("150000.00")
    assert output.adjusted_ebitda == Decimal("140000.00")
    assert output.ebit == Decimal("100000.00")
    assert output.ebitda_margin_pct == Decimal("15.00")
    assert output.adjusted_ebitda_margin_pct == Decimal("14.00")
    assert output.ebit_margin_pct == Decimal("10.00")
    assert output.currency == "EUR"


def test_zero_revenue_warns_once() -> None:
    result = run_result(revenue="0", cogs="0", operating_expenses="5000")
    output = result.data

    assert result.warnings == ["undefined_ratio"]
    assert output.ebitda == Decimal("-5000.00")
    assert output.adjusted_ebitda == Decimal("-5000.00")
    assert output.ebit == Decimal("-5000.00")
    assert output.ebitda_margin_pct is None
    assert output.adjusted_ebitda_margin_pct is None
    assert output.ebit_margin_pct is None


def test_no_depreciation_means_ebit_equals_ebitda() -> None:
    output = run(revenue="1000", cogs="400", operating_expenses="100")

    assert output.ebitda == Decimal("500.00")
    assert output.ebit == Decimal("500.00")


def test_operating_loss() -> None:
    output = run(revenue="1000", cogs="400", operating_expenses="700")

    assert output.ebitda == Decimal("-100.00")
    assert output.ebit_margin_pct == Decimal("-10.00")


def test_metadata() -> None:
    result = run_result(**BASE)

    assert result.metadata_extra == {
        "source": "user_input",
        "source_type": "user_input",
        "result_type": "calculation",
        "is_estimated": True,
        "confidence": 0.8,
        "currency": "EUR",
        "legal_disclaimer_required": True,
    }


def test_negative_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EbitdaInput.model_validate({**BASE, "cogs": "-1"})
