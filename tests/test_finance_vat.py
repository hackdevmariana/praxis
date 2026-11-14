import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.tools.finance.vat.schemas import VatInput, VatOutput
from app.tools.finance.vat.tool import calculate_vat

CTX = ToolContext(request_id="test")


def run(**kwargs: object) -> VatOutput:
    result = asyncio.run(calculate_vat(VatInput.model_validate(kwargs), CTX))
    return result.data


def test_add_vat_golden() -> None:
    output = run(amount="100")

    assert output.base_amount == Decimal("100.00")
    assert output.vat_rate == Decimal("21")
    assert output.vat_amount == Decimal("21.00")
    assert output.total_amount == Decimal("121.00")
    assert output.currency == "EUR"


def test_add_rounds_half_up() -> None:
    output = run(amount="99.99")

    assert output.vat_amount == Decimal("21.00")
    assert output.total_amount == Decimal("120.99")


def test_extract_and_remove_are_equivalent() -> None:
    extracted = run(amount="121", operation="extract")
    removed = run(amount="121", operation="remove")

    assert extracted == removed
    assert extracted.base_amount == Decimal("100.00")
    assert extracted.vat_amount == Decimal("21.00")
    assert extracted.total_amount == Decimal("121.00")


def test_extract_rounds_base() -> None:
    output = run(amount="100", operation="extract")

    assert output.base_amount == Decimal("82.64")
    assert output.vat_amount == Decimal("17.36")
    assert output.total_amount == Decimal("100.00")


def test_zero_rate() -> None:
    output = run(amount="50", rate="0")

    assert output.vat_amount == Decimal("0.00")
    assert output.total_amount == Decimal("50.00")


def test_invalid_rate_is_schema_error() -> None:
    with pytest.raises(ValidationError):
        VatInput.model_validate({"amount": "100", "rate": "101"})
