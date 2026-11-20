import asyncio
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.energy.tariff_simulator.schemas import (
    TariffSimulatorInput,
    TariffSimulatorOutput,
)
from app.tools.energy.tariff_simulator.tool import simulate_tariffs

CTX = ToolContext(request_id="test")
BASE: dict[str, Any] = {
    "annual_consumption_kwh": "3500",
    "peak_share_pct": "40",
    "contracted_power_kw": "4.6",
    "tariffs": [
        {
            "name": "A",
            "power_price_eur_kw_year": "40",
            "energy_price_peak_eur_kwh": "0.22",
            "energy_price_valley_eur_kwh": "0.14",
            "standing_charge_eur_month": "2",
        },
        {
            "name": "B",
            "power_price_eur_kw_year": "35",
            "energy_price_peak_eur_kwh": "0.19",
            "energy_price_valley_eur_kwh": "0.12",
            "standing_charge_eur_month": "3",
        },
    ],
}


def run_result(**kwargs: object) -> ToolResult[TariffSimulatorOutput]:
    return asyncio.run(simulate_tariffs(TariffSimulatorInput.model_validate(kwargs), CTX))


def run(**kwargs: object) -> TariffSimulatorOutput:
    return run_result(**kwargs).data


def test_golden_case() -> None:
    output = run(**BASE)

    assert output.annual_consumption_kwh == Decimal("3500.00")
    assert output.peak_kwh == Decimal("1400.00")
    assert output.valley_kwh == Decimal("2100.00")
    assert output.currency == "EUR"
    assert output.savings_pct_best == Decimal("11.73")
    assert [item.name for item in output.ranking] == ["B", "A"]
    best, worst = output.ranking
    assert best.power_cost == Decimal("161.00")
    assert best.energy_cost == Decimal("518.00")
    assert best.standing_cost == Decimal("36.00")
    assert best.annual_cost == Decimal("715.00")
    assert best.monthly_avg == Decimal("59.58")
    assert best.rank == 1
    assert best.is_cheapest is True
    assert best.savings_vs_most_expensive == Decimal("95.00")
    assert worst.annual_cost == Decimal("810.00")
    assert worst.is_cheapest is False
    assert worst.savings_vs_most_expensive == Decimal("0.00")


def test_zero_consumption_only_fixed_terms() -> None:
    output = run(**{**BASE, "annual_consumption_kwh": "0"})

    assert output.peak_kwh == Decimal("0.00")
    assert output.valley_kwh == Decimal("0.00")
    assert [item.annual_cost for item in output.ranking] == [
        Decimal("197.00"),
        Decimal("208.00"),
    ]


def test_all_valley_and_all_peak() -> None:
    valley = run(**{**BASE, "peak_share_pct": "0"})
    peak = run(**{**BASE, "peak_share_pct": "100"})

    assert valley.peak_kwh == Decimal("0.00")
    assert valley.valley_kwh == Decimal("3500.00")
    assert peak.peak_kwh == Decimal("3500.00")
    assert peak.valley_kwh == Decimal("0.00")


def test_ties_are_resolved_by_name() -> None:
    tariffs = [
        {
            "name": name,
            "power_price_eur_kw_year": "10",
            "energy_price_peak_eur_kwh": "0.20",
            "energy_price_valley_eur_kwh": "0.10",
        }
        for name in ("Zeta", "Alfa")
    ]
    output = run(annual_consumption_kwh="1000", contracted_power_kw="1", tariffs=tariffs)

    assert [item.name for item in output.ranking] == ["Alfa", "Zeta"]
    assert output.savings_pct_best == Decimal("0.00")


def test_zero_prices_leave_savings_pct_undefined() -> None:
    tariffs = [
        {
            "name": name,
            "power_price_eur_kw_year": "0",
            "energy_price_peak_eur_kwh": "0",
            "energy_price_valley_eur_kwh": "0",
        }
        for name in ("A", "B")
    ]
    output = run(annual_consumption_kwh="1000", contracted_power_kw="1", tariffs=tariffs)

    assert output.savings_pct_best is None
    assert output.ranking[0].annual_cost == Decimal("0.00")


def test_metadata() -> None:
    result = run_result(**BASE)

    assert result.metadata_extra == {
        "source": "user_input",
        "source_type": "user_input",
        "result_type": "comparison",
        "is_estimated": True,
        "confidence": 0.8,
        "currency": "EUR",
        "unit": "EUR/year",
        "legal_disclaimer_required": True,
    }


def test_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        TariffSimulatorInput.model_validate({**BASE, "tariffs": BASE["tariffs"][:1]})

    duplicates = [dict(BASE["tariffs"][0]), dict(BASE["tariffs"][0])]
    with pytest.raises(ValidationError):
        TariffSimulatorInput.model_validate({**BASE, "tariffs": duplicates})

    with pytest.raises(ValidationError):
        TariffSimulatorInput.model_validate({**BASE, "contracted_power_kw": "0"})

    with pytest.raises(ValidationError):
        TariffSimulatorInput.model_validate({**BASE, "peak_share_pct": "101"})

    with pytest.raises(ValidationError):
        TariffSimulatorInput.model_validate({**BASE, "annual_consumption_kwh": "-1"})

    with pytest.raises(ValidationError):
        TariffSimulatorInput.model_validate(
            {
                **BASE,
                "tariffs": [
                    {**BASE["tariffs"][0], "energy_price_peak_eur_kwh": "-0.1"},
                    BASE["tariffs"][1],
                ],
            }
        )
