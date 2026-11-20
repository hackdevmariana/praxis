import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.energy.carbon_footprint.schemas import CarbonInput, CarbonOutput
from app.tools.energy.carbon_footprint.tool import calculate_carbon_footprint

CTX = ToolContext(request_id="test")
BASE = {
    "electricity_kwh": "10000",
    "gas_kwh": "5000",
    "diesel_liters": "500",
    "gasoline_liters": "200",
    "waste_kg": "300",
    "transport_km": "2000",
    "period_start": "2026-01-01",
    "period_end": "2026-12-31",
}


def run_result(**kwargs: object) -> ToolResult[CarbonOutput]:
    return asyncio.run(calculate_carbon_footprint(CarbonInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> CarbonOutput:
    return run_result(**kwargs).data


def test_golden_case() -> None:
    result = run_result(**BASE)

    assert result.data.scope1_kgco2e == Decimal("2812.00")
    assert result.data.scope2_kgco2e == Decimal("1500.00")
    assert result.data.scope3_kgco2e == Decimal("390.00")
    assert result.data.total_kgco2e == Decimal("4702.00")
    assert result.data.intensity_kgco2e_per_kwh == Decimal("0.3135")
    assert result.data.period_start is not None
    assert result.data.period_start.isoformat() == "2026-01-01"
    assert result.data.period_end is not None
    assert result.data.period_end.isoformat() == "2026-12-31"
    assert [item.activity for item in result.data.by_source] == [
        "electricity",
        "natural_gas",
        "diesel",
        "gasoline",
        "waste",
        "transport",
    ]
    assert result.data.by_source[0].factor == Decimal("0.150")
    assert result.data.by_source[0].emissions_kgco2e == Decimal("1500.00")
    assert result.warnings == ["possible_double_counting"]


def test_electricity_only() -> None:
    output = run(electricity_kwh="1000", factor_overrides=None)

    assert output.scope2_kgco2e == Decimal("150.00")
    assert output.total_kgco2e == Decimal("150.00")
    assert output.intensity_kgco2e_per_kwh == Decimal("0.1500")
    assert len(output.by_source) == 1
    assert output.by_source[0].activity == "electricity"


def test_custom_factors() -> None:
    result = run_result(electricity_kwh="10000", factor_overrides={"electricity": "0.10"})

    assert result.data.scope2_kgco2e == Decimal("1000.00")
    assert result.data.total_kgco2e == Decimal("1000.00")
    assert result.warnings == ["custom_factors"]
    assert result.metadata_extra["factors_source"] == "custom"


def test_no_consumption_has_no_intensity() -> None:
    output = run()

    assert output.total_kgco2e == Decimal("0.00")
    assert output.intensity_kgco2e_per_kwh is None
    assert output.by_source == []


def test_gasoline_and_transport_also_warns_double_counting() -> None:
    result = run_result(gasoline_liters="10", transport_km="100")

    assert result.warnings == ["possible_double_counting"]


def test_metadata() -> None:
    result = run_result(electricity_kwh="1000")

    assert result.metadata_extra == {
        "source": "deterministic",
        "source_type": "deterministic",
        "result_type": "calculation",
        "is_estimated": True,
        "confidence": 0.7,
        "unit": "kgCO2e",
        "factors_version": "2026.1",
        "factors_source": "default",
        "legal_disclaimer_required": True,
    }


def test_invalid_periods_and_factors() -> None:
    with pytest.raises(ValidationError):
        CarbonInput.model_validate({"period_start": "2026-01-01"})

    with pytest.raises(ValidationError):
        CarbonInput.model_validate({"period_start": "2026-12-31", "period_end": "2026-01-01"})

    with pytest.raises(ValidationError):
        CarbonInput.model_validate({"factor_overrides": {"electricity": "-1"}})

    with pytest.raises(ValidationError):
        CarbonInput.model_validate({"factor_overrides": {"unknown": "1"}})

    with pytest.raises(ValidationError):
        CarbonInput.model_validate({"electricity_kwh": "-1"})
