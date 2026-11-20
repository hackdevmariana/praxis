import asyncio
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.context import ToolContext
from app.result import ToolResult
from app.tools.procurement.detect_price_increase.schemas import (
    PriceIncreaseInput,
    PriceIncreaseOutput,
)
from app.tools.procurement.detect_price_increase.tool import detect_price_increase

CTX = ToolContext(request_id="test", scopes=frozenset({"procurement.read"}))


def run_result(**kwargs: object) -> ToolResult[PriceIncreaseOutput]:
    return asyncio.run(detect_price_increase(PriceIncreaseInput.model_validate(kwargs), CTX))


def item(
    description: str,
    previous: str | Decimal,
    current: str | Decimal,
    *,
    quantity: str | Decimal | None = None,
    supplier: str = "Proveedor",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "supplier": supplier,
        "description": description,
        "previous_unit_price": previous,
        "current_unit_price": current,
    }
    if quantity is not None:
        payload["annual_quantity"] = quantity
    return payload


def test_golden_case() -> None:
    result = run_result(
        threshold_pct="10",
        items=[
            item("Harina", "10", "10.5", quantity="12000", supplier="Molinos S.A."),
            item("Aceite", "20", "24", quantity="5000", supplier="Aceites S.L."),
            item("Detergente", "5", "6.5", quantity="2000", supplier="Limpia S.L."),
            item("Producto nuevo", "0", "3", supplier="Nuevo S.L."),
        ],
    )
    output = result.data

    assert [alert.description for alert in output.alerts] == [
        "Detergente",
        "Aceite",
        "Harina",
        "Producto nuevo",
    ]
    assert output.anomalous_count == 2
    assert output.high_count == 2
    assert output.medium_count == 0
    assert output.new_price_count == 1
    assert output.currency == "EUR"
    detergente, aceite, harina, nuevo = output.alerts
    assert detergente.change_amount == Decimal("1.50")
    assert detergente.change_pct == Decimal("30.00")
    assert detergente.annual_impact == Decimal("3000.00")
    assert detergente.is_anomalous is True
    assert detergente.severity == "high"
    assert aceite.change_pct == Decimal("20.00")
    assert aceite.annual_impact == Decimal("20000.00")
    assert harina.change_pct == Decimal("5.00")
    assert harina.is_anomalous is False
    assert harina.severity == "low"
    assert nuevo.change_pct is None
    assert nuevo.annual_impact is None
    assert nuevo.change_amount == Decimal("3.00")
    assert nuevo.is_new_price is True
    assert nuevo.severity == "new_price"


def test_threshold_boundaries_produce_medium_and_high() -> None:
    output = run_result(
        threshold_pct="10",
        items=[
            item("Medio", "100", "110"),
            item("Alto", "100", "120"),
            item("Bajo", "100", "109.99"),
        ],
    ).data

    assert [alert.severity for alert in output.alerts] == ["high", "medium", "low"]
    assert output.anomalous_count == 2
    assert output.medium_count == 1
    assert output.high_count == 1


def test_price_drop_is_not_anomalous_and_new_price_can_have_impact() -> None:
    output = run_result(
        items=[item("Bajada", "20", "18"), item("Nuevo", "0", "5", quantity="100")],
    ).data

    bajada, nuevo = output.alerts
    assert bajada.change_pct == Decimal("-10.00")
    assert bajada.annual_impact is None
    assert bajada.is_anomalous is False
    assert bajada.severity == "low"
    assert nuevo.change_pct is None
    assert nuevo.annual_impact == Decimal("500.00")


def test_equal_percentages_are_sorted_by_description() -> None:
    output = run_result(items=[item("Zeta", "10", "12"), item("Alfa", "10", "12")]).data

    assert [alert.description for alert in output.alerts] == ["Alfa", "Zeta"]


def test_metadata_is_analysis_and_estimated() -> None:
    result = run_result(items=[item("Harina", "10", "11")])

    assert result.metadata_extra["source"] == "user_input"
    assert result.metadata_extra["result_type"] == "analysis"
    assert result.metadata_extra["is_estimated"] is True
    assert result.metadata_extra["legal_disclaimer_required"] is False
    assert result.warnings == []


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [item("A", "10", "11")], "threshold_pct": "0"},
        {"items": [item("A", "-1", "11")]},
        {"items": [item("A", "10", "11")], "threshold_pct": "101"},
        {"items": []},
        {"items": [item("A", "10", "11", quantity="-1")]},
        {"items": [item(f"A{i}", "10", "11") for i in range(501)]},
    ],
)
def test_invalid_params_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PriceIncreaseInput.model_validate(payload)


@settings(max_examples=40, deadline=None)
@given(
    previous=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=2),
    current=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=2),
)
def test_severity_constraints(previous: Decimal, current: Decimal) -> None:
    output = run_result(items=[item("Producto", previous, current)]).data
    alert = output.alerts[0]

    if alert.change_pct is None:
        assert alert.is_new_price is True
        assert alert.is_anomalous is False
        assert alert.severity == "new_price"
    else:
        assert alert.is_anomalous is (alert.change_pct >= Decimal("10"))
        if alert.severity == "high":
            assert alert.change_pct >= Decimal("20")
        if alert.severity == "medium":
            assert Decimal("10") <= alert.change_pct < Decimal("20")
