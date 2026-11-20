import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.energy.self_consumption_payback.schemas import (
    SelfConsumptionInput,
    SelfConsumptionOutput,
)
from app.tools.energy.self_consumption_payback.tool import calculate_self_consumption_payback

CTX = ToolContext(request_id="test")
BASE = {
    "installation_kwp": "5",
    "annual_production_kwh": "7000",
    "self_consumption_pct": "60",
    "capex": "5000",
    "electricity_price_eur_kwh": "0.18",
    "export_price_eur_kwh": "0.06",
    "annual_opex": "50",
    "degradation_pct": "0.5",
    "years": 25,
    "discount_rate_pct": "3",
}


def run_result(**kwargs: object) -> ToolResult[SelfConsumptionOutput]:
    params = SelfConsumptionInput.model_validate({**BASE, **kwargs})
    return asyncio.run(calculate_self_consumption_payback(params, CTX))


def run(**kwargs: object) -> SelfConsumptionOutput:
    return run_result(**kwargs).data


def test_golden_case() -> None:
    output = run()

    assert output.year1_savings == Decimal("874.00")
    assert output.simple_payback_years == Decimal("5.72")
    assert output.payback_years == Decimal("5.79")
    assert output.npv == Decimal("9405.61")
    assert output.irr_pct == Decimal("16.62")
    assert output.currency == "EUR"
    assert len(output.cashflows) == 25
    first = output.cashflows[0]
    assert (first.year, first.production_kwh, first.self_consumed_kwh) == (
        1,
        Decimal("7000.00"),
        Decimal("4200.00"),
    )
    assert first.exported_kwh == Decimal("2800.00")
    assert first.savings == Decimal("874.00")
    assert first.cumulative_savings == Decimal("874.00")
    sixth = output.cashflows[5]
    assert (sixth.production_kwh, sixth.savings, sixth.cumulative_savings) == (
        Decimal("6826.74"),
        Decimal("851.13"),
        Decimal("5175.16"),
    )


def test_negative_savings_have_no_payback_or_irr() -> None:
    output = run(annual_opex="1000")

    assert output.year1_savings == Decimal("-76.00")
    assert output.simple_payback_years is None
    assert output.payback_years is None
    assert output.irr_pct is None
    assert output.cashflows[0].cumulative_savings == Decimal("-76.00")


def test_zero_capex_has_immediate_payback() -> None:
    output = run(capex="0")

    assert output.payback_years == Decimal("0.00")
    assert output.simple_payback_years == Decimal("0.00")
    assert output.irr_pct is None
    assert output.npv > 0


def test_horizon_too_short_leaves_payback_undefined() -> None:
    output = run(years=5)

    assert output.payback_years is None
    assert len(output.cashflows) == 5


def test_savings_below_capex_have_no_irr() -> None:
    output = run(annual_opex="800")

    assert output.cashflows[0].savings > 0
    assert output.payback_years is None
    assert output.irr_pct is None


def test_self_consumption_boundaries() -> None:
    full = run(self_consumption_pct="100")
    none = run(self_consumption_pct="0", export_price_eur_kwh="0.06")
    no_export = run(export_price_eur_kwh="0")

    assert full.cashflows[0].exported_kwh == Decimal("0.00")
    assert none.cashflows[0].self_consumed_kwh == Decimal("0.00")
    assert none.cashflows[0].exported_kwh == Decimal("7000.00")
    assert no_export.cashflows[0].savings < full.cashflows[0].savings


def test_high_irr_expands_the_search_interval() -> None:
    output = run(electricity_price_eur_kwh="5", export_price_eur_kwh="1")

    assert output.irr_pct is not None
    assert output.irr_pct > Decimal("100")


def test_metadata() -> None:
    result = run_result()

    assert result.metadata_extra == {
        "source": "deterministic",
        "source_type": "deterministic",
        "result_type": "simulation",
        "is_estimated": True,
        "confidence": 0.75,
        "currency": "EUR",
        "unit": "EUR",
        "legal_disclaimer_required": True,
    }


def test_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        SelfConsumptionInput.model_validate({**BASE, "self_consumption_pct": "101"})

    with pytest.raises(ValidationError):
        SelfConsumptionInput.model_validate({**BASE, "degradation_pct": "11"})

    with pytest.raises(ValidationError):
        SelfConsumptionInput.model_validate({**BASE, "years": 41})

    with pytest.raises(ValidationError):
        SelfConsumptionInput.model_validate({**BASE, "capex": "-1"})

    with pytest.raises(ValidationError):
        SelfConsumptionInput.model_validate({**BASE, "annual_production_kwh": "0"})
