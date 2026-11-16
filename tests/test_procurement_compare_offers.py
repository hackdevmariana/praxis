import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ToolError
from app.tools.procurement.compare_offers.schemas import (
    CompareOffersInput,
    CompareOffersOutput,
)
from app.tools.procurement.compare_offers.tool import compare_offers

CTX = ToolContext(request_id="test")

OFFERS = [
    {
        "supplier": "A",
        "monthly_price": "100",
        "permanence_months": 24,
        "cancellation_cost": "500",
        "year2_price": "100",
        "year3_price": "110",
    },
    {
        "supplier": "B",
        "monthly_price": "90",
        "permanence_months": 36,
        "cancellation_cost": "1000",
        "year2_price": "95",
        "year3_price": "100",
    },
    {
        "supplier": "C",
        "monthly_price": "110",
        "permanence_months": 0,
        "cancellation_cost": "0",
        "upfront_cost": "200",
    },
]


def run_result(**kwargs: object) -> CompareOffersOutput:
    return asyncio.run(compare_offers(CompareOffersInput.model_validate(kwargs), CTX)).data


def test_three_offer_golden() -> None:
    output = run_result(offers=OFFERS)

    assert output.ranking == [
        {"rank": 1, "supplier": "C", "total_cost": Decimal("6800.00")},
        {"rank": 2, "supplier": "B", "total_cost": Decimal("6820.00")},
        {"rank": 3, "supplier": "A", "total_cost": Decimal("6860.00")},
    ]
    table = {row.supplier: row for row in output.normalized_table}
    assert table["C"].recurring_cost == Decimal("6600.00")
    assert table["C"].one_off_cost == Decimal("200.00")
    assert table["C"].monthly_cost == Decimal("113.33")
    assert table["C"].is_cheapest is True
    assert table["C"].savings_vs_most_expensive == Decimal("60.00")
    assert table["A"].savings_vs_most_expensive == Decimal("0.00")
    assert table["B"].rank == 2


def test_normalize_by_annual_uses_annual_metric() -> None:
    output = run_result(offers=OFFERS, normalize_by="annual")

    assert [row["supplier"] for row in output.ranking] == ["C", "B", "A"]
    assert output.ranking[0]["annual_cost"] == Decimal("1360.00")


def test_two_offers_warn_few_offers() -> None:
    result = asyncio.run(
        compare_offers(
            CompareOffersInput.model_validate(
                {
                    "offers": [
                        {"supplier": "A", "monthly_price": "100"},
                        {"supplier": "B", "monthly_price": "90"},
                    ]
                }
            ),
            CTX,
        )
    )

    assert "few_offers" in result.warnings


def test_vat_included_is_normalized_and_mixed_basis_warns() -> None:
    result = asyncio.run(
        compare_offers(
            CompareOffersInput.model_validate(
                {
                    "years": 1,
                    "offers": [
                        {
                            "supplier": "X",
                            "monthly_price": "121",
                            "vat_included": True,
                            "vat_rate": "21",
                        },
                        {"supplier": "Y", "monthly_price": "105"},
                    ],
                }
            ),
            CTX,
        )
    )

    table = {row.supplier: row for row in result.data.normalized_table}
    assert table["X"].monthly_price_net == Decimal("100.00")
    assert table["X"].total_cost == Decimal("1200.00")
    assert table["Y"].total_cost == Decimal("1260.00")
    assert result.data.ranking[0]["supplier"] == "X"
    assert "few_offers" in result.warnings
    assert "mixed_vat_basis_normalized" in result.warnings


def test_currency_mismatch_is_domain_error() -> None:
    with pytest.raises(ToolError) as error:
        asyncio.run(
            compare_offers(
                CompareOffersInput.model_validate(
                    {
                        "offers": [
                            {"supplier": "A", "monthly_price": "100"},
                            {
                                "supplier": "B",
                                "monthly_price": "100",
                                "currency": "USD",
                            },
                        ]
                    }
                ),
                CTX,
            )
        )

    assert error.value.code == "currency_mismatch"


def test_more_than_five_offers_is_schema_error() -> None:
    with pytest.raises(ValidationError):
        CompareOffersInput.model_validate(
            {"offers": [{"supplier": str(i), "monthly_price": "10"} for i in range(6)]}
        )


def test_year_prices_fall_back_to_previous_year() -> None:
    output = run_result(
        years=3,
        offers=[
            {"supplier": "A", "monthly_price": "100"},
            {"supplier": "B", "monthly_price": "100", "year2_price": "50"},
        ],
    )

    table = {row.supplier: row for row in output.normalized_table}
    assert table["A"].recurring_cost == Decimal("3600.00")
    assert table["B"].recurring_cost == Decimal("2400.00")
    assert output.ranking[0]["supplier"] == "B"
