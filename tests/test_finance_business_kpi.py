import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.finance.business_kpi.schemas import BusinessKpiInput, BusinessKpiOutput
from app.tools.finance.business_kpi.tool import calculate_business_kpi

CTX = ToolContext(request_id="test")

BASE = {
    "revenue": "1000000",
    "cogs": "600000",
    "operating_expenses": "250000",
    "depreciation_amortization": "50000",
    "receivables": "120000",
    "payables": "80000",
    "inventory": "90000",
    "cash": "60000",
    "current_liabilities": "150000",
    "period_days": 365,
}


def run_result(**kwargs: object) -> ToolResult[BusinessKpiOutput]:
    return asyncio.run(calculate_business_kpi(BusinessKpiInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> BusinessKpiOutput:
    return run_result(**kwargs).data


def test_golden_case() -> None:
    output = run(**BASE)

    assert output.gross_profit == Decimal("400000.00")
    assert output.gross_margin_pct == Decimal("40.00")
    assert output.ebit == Decimal("150000.00")
    assert output.ebit_margin_pct == Decimal("15.00")
    assert output.ebitda == Decimal("200000.00")
    assert output.dso_days == Decimal("43.80")
    assert output.dpo_days == Decimal("48.67")
    assert output.dio_days == Decimal("54.75")
    assert output.cash_conversion_cycle_days == Decimal("49.88")
    assert output.current_ratio == Decimal("1.80")
    assert output.working_capital == Decimal("120000.00")
    assert output.currency == "EUR"


def test_zero_revenue_warns_once() -> None:
    result = run_result(
        revenue="0",
        cogs="0",
        operating_expenses="1000",
        current_liabilities="0",
    )
    output = result.data

    assert result.warnings == ["undefined_ratio"]
    assert output.gross_margin_pct is None
    assert output.ebit == Decimal("-1000.00")
    assert output.ebitda == Decimal("-1000.00")
    assert output.dso_days is None
    assert output.current_ratio is None
    assert output.working_capital == Decimal("0.00")


def test_zero_cogs_leaves_dpo_and_dio_undefined() -> None:
    output = run(revenue="1000", cogs="0", operating_expenses="100", payables="50", inventory="50")

    assert output.dpo_days is None
    assert output.dio_days is None
    assert output.cash_conversion_cycle_days is None


def test_loss_is_negative_ebit() -> None:
    output = run(revenue="1000", cogs="600", operating_expenses="500")

    assert output.gross_profit == Decimal("400.00")
    assert output.ebit == Decimal("-100.00")
    assert output.ebitda == Decimal("-100.00")


def test_period_days_scales_cycle() -> None:
    output = run(**{**BASE, "period_days": 90})

    assert output.dso_days == Decimal("10.80")
    assert output.dpo_days == Decimal("12.00")
    assert output.dio_days == Decimal("13.50")
    assert output.cash_conversion_cycle_days == Decimal("12.30")


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


def test_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        BusinessKpiInput.model_validate({**BASE, "revenue": "-1"})

    with pytest.raises(ValidationError):
        BusinessKpiInput.model_validate({**BASE, "period_days": 29})

    with pytest.raises(ValidationError):
        BusinessKpiInput.model_validate({**BASE, "period_days": 367})
