import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx
import time_machine
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.result import ToolResult
from app.tools.weather.forecast.schemas import (
    WeatherInput,
    WeatherOutput,
)
from app.tools.weather.forecast.tool import FORECAST_URL, forecast_weather

CTX = ToolContext(request_id="test")
FIXTURE = Path(__file__).parent / "fixtures" / "open-meteo-2026-11-13-madrid.json"
PAYLOAD = json.loads(FIXTURE.read_text(encoding="utf-8"))


def run(**kwargs: object) -> ToolResult[WeatherOutput]:
    return asyncio.run(forecast_weather(WeatherInput.model_validate(kwargs), CTX))


def mock_open_meteo() -> respx.Route:
    return respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=PAYLOAD))


@respx.mock
def test_daily_golden() -> None:
    route = mock_open_meteo()
    result = run(latitude=40.4168, longitude=-3.7038, days=2)
    output = result.data

    assert output.location.latitude == 40.4168
    assert output.location.longitude == -3.7038
    assert output.location.elevation == 667.0
    assert output.location.timezone == "Europe/Madrid"
    assert output.granularity == "daily"
    assert len(output.points) == 2
    assert output.points[0].time == "2026-11-13"
    assert output.points[0].values == {
        "temperature_2m_max": 17.2,
        "temperature_2m_min": 8.4,
        "apparent_temperature_max": 16.8,
        "precipitation_probability_max": 10,
        "precipitation_sum": 0.0,
        "wind_speed_10m_max": 14.5,
        "relative_humidity_2m_mean": 61,
        "shortwave_radiation_sum": 8.9,
        "cloud_cover_mean": 35,
        "uv_index_max": 2.1,
    }
    assert result.metadata_extra["source"] == "open_meteo"
    assert result.metadata_extra["is_estimated"] is True
    assert result.metadata_extra["units"]["temperature"] == "°C"
    assert result.metadata_extra["units"]["shortwave_radiation"] == "MJ/m²"
    assert route.call_count == 1


@respx.mock
def test_hourly_golden_uses_local_offset() -> None:
    mock_open_meteo()
    result = run(
        latitude=40.4168,
        longitude=-3.7038,
        days=1,
        granularity="hourly",
        variables=["temperature_2m"],
    )
    output = result.data

    assert output.granularity == "hourly"
    assert len(output.points) == 24
    assert output.points[0].time == "2026-11-13T00:00:00+01:00"
    assert output.points[0].values == {"temperature_2m": 9.1}
    assert output.points[12].time == "2026-11-13T12:00:00+01:00"
    assert output.points[12].values == {"temperature_2m": 16.9}


@respx.mock
def test_daily_variables_filter_request_and_output() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["daily"] = request.url.params["daily"]
        return httpx.Response(200, json=PAYLOAD)

    respx.get(FORECAST_URL).mock(side_effect=handler)
    result = run(
        latitude=40.4168,
        longitude=-3.7038,
        days=1,
        variables=["temperature_2m", "precipitation"],
    )

    assert captured["daily"] == ("temperature_2m_max,temperature_2m_min,precipitation_sum")
    assert set(result.data.points[0].values) == {
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    }


def test_invalid_timezone_is_invalid_params() -> None:
    with pytest.raises(ToolError) as error:
        run(
            latitude=40.4168,
            longitude=-3.7038,
            timezone="Europe/Atlantis",
        )

    assert error.value.code == ErrorCode.INVALID_PARAMS


@pytest.mark.parametrize(
    "kwargs",
    [
        {"latitude": 100, "longitude": -3.7038},
        {"latitude": 40.4168, "longitude": -3.7038, "days": 8},
        {"latitude": 40.4168, "longitude": -3.7038, "days": 0},
    ],
)
def test_out_of_range_inputs_are_schema_errors(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        WeatherInput.model_validate(kwargs)


@respx.mock
def test_provider_5xx_is_unavailable() -> None:
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(502))

    with pytest.raises(ToolError) as error:
        run(latitude=40.4168, longitude=-3.7038)

    assert error.value.code == ErrorCode.PROVIDER_UNAVAILABLE


@respx.mock
def test_provider_timeout_is_unavailable() -> None:
    respx.get(FORECAST_URL).mock(side_effect=httpx.ReadTimeout("boom"))

    with pytest.raises(ToolError) as error:
        run(latitude=40.4168, longitude=-3.7038)

    assert error.value.code == ErrorCode.PROVIDER_UNAVAILABLE


@respx.mock
def test_provider_429_is_rate_limited() -> None:
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(429))

    with pytest.raises(ToolError) as error:
        run(latitude=40.4168, longitude=-3.7038)

    assert error.value.code == ErrorCode.RATE_LIMITED


@respx.mock
def test_second_call_uses_cache() -> None:
    route = mock_open_meteo()
    with time_machine.travel("2026-11-13T10:00:00Z", tick=False):
        run(latitude=40.4168, longitude=-3.7038, days=2)
        run(latitude=40.4168, longitude=-3.7038, days=2)

    assert route.call_count == 1
