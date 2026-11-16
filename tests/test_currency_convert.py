import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
import time_machine

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.result import ToolResult
from app.tools.currency.convert.schemas import CurrencyConvertInput, CurrencyConvertOutput
from app.tools.currency.convert.tool import ECB_URL, convert_currency

CTX = ToolContext(request_id="test")
FIXTURE = Path(__file__).parent / "fixtures" / "ecb-2026-11-13.csv"
CSV = FIXTURE.read_text(encoding="utf-8")


def run(**kwargs: object) -> ToolResult[CurrencyConvertOutput]:
    return asyncio.run(convert_currency(CurrencyConvertInput.model_validate(kwargs), CTX))


def mock_ecb() -> respx.Route:
    return respx.get(ECB_URL).mock(return_value=httpx.Response(200, text=CSV))


@respx.mock
def test_eur_to_usd_golden() -> None:
    route = mock_ecb()
    result = run(
        amount="100",
        from_currency="EUR",
        to_currency="USD",
        date="2026-11-13",
    )

    assert result.data.amount == Decimal("100.00")
    assert result.data.converted_amount == Decimal("108.50")
    assert result.data.rate == Decimal("1.085000")
    assert result.data.rate_date == date(2026, 11, 13)
    assert result.metadata_extra["source"] == "ecb"
    assert result.metadata_extra["currency"] == "USD"
    assert route.call_count == 1


@respx.mock
def test_usd_to_eur_golden() -> None:
    mock_ecb()
    result = run(
        amount="100",
        from_currency="USD",
        to_currency="EUR",
        date="2026-11-13",
    )

    assert result.data.converted_amount == Decimal("92.17")
    assert result.data.rate == Decimal("0.921659")


@respx.mock
def test_cross_rate_golden() -> None:
    mock_ecb()
    result = run(
        amount="100",
        from_currency="USD",
        to_currency="GBP",
        date="2026-11-13",
    )

    assert result.data.converted_amount == Decimal("79.72")
    assert result.data.rate == Decimal("0.797235")


@respx.mock
def test_weekend_uses_previous_business_day() -> None:
    mock_ecb()
    result = run(
        amount="250",
        from_currency="EUR",
        to_currency="EUR",
        date="2026-11-14",
    )

    assert result.data.converted_amount == Decimal("250.00")
    assert result.data.rate == Decimal("1.000000")
    assert result.data.rate_date == date(2026, 11, 13)


@respx.mock
def test_lowercase_codes_are_normalized() -> None:
    mock_ecb()
    result = run(
        amount="100",
        from_currency="eur",
        to_currency="usd",
        date="2026-11-13",
    )

    assert result.data.from_currency == "EUR"
    assert result.data.to_currency == "USD"
    assert result.data.converted_amount == Decimal("108.50")


@respx.mock
def test_zero_amount() -> None:
    mock_ecb()
    result = run(
        amount="0",
        from_currency="EUR",
        to_currency="USD",
        date="2026-11-13",
    )

    assert result.data.converted_amount == Decimal("0.00")


@respx.mock
def test_unsupported_currency_does_not_call_provider() -> None:
    route = respx.get(ECB_URL)

    with pytest.raises(ToolError) as error:
        run(amount="100", from_currency="EUR", to_currency="BTC")

    assert error.value.code == "unsupported_currency"
    assert not route.called


@time_machine.travel("2026-11-13T10:00:00Z", tick=False)
def test_future_date_is_rejected() -> None:
    with pytest.raises(ToolError) as error:
        run(
            amount="100",
            from_currency="EUR",
            to_currency="USD",
            date="2026-11-14",
        )

    assert error.value.code == ErrorCode.INVALID_PARAMS


@respx.mock
def test_provider_5xx_is_unavailable() -> None:
    respx.get(ECB_URL).mock(return_value=httpx.Response(503))

    with pytest.raises(ToolError) as error:
        run(amount="100", from_currency="EUR", to_currency="USD", date="2026-11-13")

    assert error.value.code == ErrorCode.PROVIDER_UNAVAILABLE


@respx.mock
def test_provider_timeout_is_unavailable() -> None:
    respx.get(ECB_URL).mock(side_effect=httpx.ConnectTimeout("boom"))

    with pytest.raises(ToolError) as error:
        run(amount="100", from_currency="EUR", to_currency="USD", date="2026-11-13")

    assert error.value.code == ErrorCode.PROVIDER_UNAVAILABLE


@respx.mock
def test_provider_429_is_rate_limited() -> None:
    respx.get(ECB_URL).mock(return_value=httpx.Response(429))

    with pytest.raises(ToolError) as error:
        run(amount="100", from_currency="EUR", to_currency="USD", date="2026-11-13")

    assert error.value.code == ErrorCode.RATE_LIMITED


@respx.mock
def test_second_call_uses_cache() -> None:
    route = mock_ecb()
    with time_machine.travel("2026-11-13T10:00:00Z", tick=False):
        run(amount="100", from_currency="EUR", to_currency="USD", date="2026-11-13")
        run(amount="200", from_currency="EUR", to_currency="USD", date="2026-11-13")

    assert route.call_count == 1
