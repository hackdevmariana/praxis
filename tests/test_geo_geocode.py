import asyncio

import httpx
import pytest
import respx
import time_machine
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.result import ToolResult
from app.tools.geo.geocode.schemas import GeocodeInput, GeocodeOutput
from app.tools.geo.geocode.tool import (
    CARTO_BASE,
    NOMINATIM_BASE,
    geocode,
)

CTX = ToolContext(request_id="test")

CARTO_FORWARD = {
    "lat": 40.4155,
    "lon": -3.7074,
    "address": "CALLE MAYOR 1, 28013 MADRID",
    "ine_code": "28079",
    "municipio": "Madrid",
    "provincia": "Madrid",
    "codPostal": "28013",
    "confianza": 0.98,
}
CARTO_REVERSE = {
    "lat": 40.4155,
    "lon": -3.7074,
    "address": "CALLE MAYOR 1, 28013 MADRID",
    "ine_code": "28079",
    "municipio": "Madrid",
    "provincia": "Madrid",
    "codPostal": "28013",
    "confianza": 0.95,
}
NOMINATIM_FORWARD = [
    {
        "lat": "40.4155",
        "lon": "-3.7074",
        "display_name": "Calle Mayor 1, Madrid",
        "importance": 0.91,
        "address": {"city": "Madrid", "state": "Madrid", "postcode": "28013"},
    }
]


def run(**kwargs: object) -> ToolResult[GeocodeOutput]:
    return asyncio.run(geocode(GeocodeInput.model_validate(kwargs), CTX))


@respx.mock
def test_forward_golden() -> None:
    route = respx.get(f"{CARTO_BASE}/candidates").mock(
        return_value=httpx.Response(200, json=[CARTO_FORWARD])
    )
    result = run(address="Calle Mayor 1, Madrid")
    output = result.data

    assert output.mode == "forward"
    assert len(output.results) == 1
    item = output.results[0]
    assert item.latitude == 40.4155
    assert item.longitude == -3.7074
    assert item.normalized_address == "CALLE MAYOR 1, 28013 MADRID"
    assert item.ine_code == "28079"
    assert item.municipality == "Madrid"
    assert item.province == "Madrid"
    assert item.postal_code == "28013"
    assert item.confidence == 0.98
    assert item.source == "cartociudad"
    assert result.metadata_extra["source"] == "cartociudad"
    assert result.metadata_extra["confidence"] == 0.98
    assert result.metadata_extra["attribution"] == "Geocodificación: CartoCiudad (IGN)"
    assert route.call_count == 1


@respx.mock
def test_reverse_golden() -> None:
    respx.get(f"{CARTO_BASE}/reverseGeocode").mock(
        return_value=httpx.Response(200, json=CARTO_REVERSE)
    )
    result = run(latitude=40.4155, longitude=-3.7074)

    assert result.data.mode == "reverse"
    assert len(result.data.results) == 1
    assert result.data.results[0].normalized_address == "CALLE MAYOR 1, 28013 MADRID"
    assert result.data.results[0].confidence == 0.95


@respx.mock
def test_no_results_returns_warning() -> None:
    respx.get(f"{CARTO_BASE}/candidates").mock(return_value=httpx.Response(200, json=[]))
    result = run(address="zzzzzzzz")

    assert result.data.results == []
    assert result.warnings == ["no_results"]


@respx.mock
def test_primary_failure_uses_nominatim_fallback() -> None:
    respx.get(f"{CARTO_BASE}/candidates").mock(return_value=httpx.Response(503))
    fallback = respx.get(f"{NOMINATIM_BASE}/search").mock(
        return_value=httpx.Response(200, json=NOMINATIM_FORWARD)
    )
    result = run(address="Calle Mayor 1, Madrid")

    assert result.data.results[0].source == "nominatim"
    assert result.data.results[0].municipality == "Madrid"
    assert result.warnings == ["fallback_source_used"]
    assert result.metadata_extra["source"] == "nominatim"
    assert fallback.call_count == 1


@respx.mock
def test_rate_limited_primary_uses_fallback() -> None:
    respx.get(f"{CARTO_BASE}/candidates").mock(return_value=httpx.Response(429))
    respx.get(f"{NOMINATIM_BASE}/search").mock(
        return_value=httpx.Response(200, json=NOMINATIM_FORWARD)
    )
    result = run(address="Calle Mayor 1, Madrid")

    assert result.warnings == ["fallback_source_used"]
    assert result.metadata_extra["source"] == "nominatim"


@respx.mock
def test_both_providers_fail_is_unavailable() -> None:
    respx.get(f"{CARTO_BASE}/candidates").mock(return_value=httpx.Response(503))
    respx.get(f"{NOMINATIM_BASE}/search").mock(return_value=httpx.Response(502))

    with pytest.raises(ToolError) as error:
        run(address="Calle Mayor 1, Madrid")

    assert error.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert set(error.value.details) == {"primary", "fallback"}


@respx.mock
def test_limit_and_municipality_filter() -> None:
    second = {
        **CARTO_FORWARD,
        "lat": 40.1,
        "address": "CALLE MAYOR 1, 28080 MADRID",
        "ine_code": "28080",
    }
    third = {
        **CARTO_FORWARD,
        "lat": 40.2,
        "address": "CALLE MAYOR 1, 28079 MADRID",
        "ine_code": "28079",
    }
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["municipio"] = request.url.params["municipio"]
        return httpx.Response(200, json=[CARTO_FORWARD, second, third])

    respx.get(f"{CARTO_BASE}/candidates").mock(side_effect=handler)
    result = run(
        address="Calle Mayor 1",
        municipality_code="28079",
        limit=2,
    )

    assert captured["municipio"] == "28079"
    assert len(result.data.results) == 2
    assert {item.ine_code for item in result.data.results} == {"28079"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"address": "Calle Mayor 1", "latitude": 40.4, "longitude": -3.7},
        {},
        {"latitude": 40.4},
        {"address": "Calle Mayor 1", "municipality_code": "123"},
        {"latitude": 95, "longitude": -3.7},
    ],
)
def test_invalid_inputs_are_schema_errors(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GeocodeInput.model_validate(kwargs)


@respx.mock
def test_second_call_uses_cache() -> None:
    route = respx.get(f"{CARTO_BASE}/candidates").mock(
        return_value=httpx.Response(200, json=[CARTO_FORWARD])
    )
    with time_machine.travel("2026-11-13T10:00:00Z", tick=False):
        run(address="Calle Mayor 1, Madrid")
        run(address="Calle Mayor 1, Madrid")

    assert route.call_count == 1
