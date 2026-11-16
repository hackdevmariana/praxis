import json
from datetime import datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.cache import CacheEntry, TTLCache
from app.providers.http import get_json
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.weather.forecast.schemas import (
    Granularity,
    Location,
    WeatherInput,
    WeatherOutput,
    WeatherPoint,
    WeatherVariable,
)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_SOURCEFORECAST_URL = "https://api.open-meteo.com/v1"
_ATTRIBUTION = "Weather data by Open-Meteo (https://open-meteo.com)"
_CACHE_TTL = timedelta(minutes=30)

_DAILY_KEYS: dict[WeatherVariable, tuple[str, ...]] = {
    WeatherVariable.temperature_2m: (
        "temperature_2m_max",
        "temperature_2m_min",
    ),
    WeatherVariable.apparent_temperature: ("apparent_temperature_max",),
    WeatherVariable.precipitation_probability: ("precipitation_probability_max",),
    WeatherVariable.precipitation: ("precipitation_sum",),
    WeatherVariable.wind_speed_10m: ("wind_speed_10m_max",),
    WeatherVariable.relative_humidity_2m: ("relative_humidity_2m_mean",),
    WeatherVariable.shortwave_radiation: ("shortwave_radiation_sum",),
    WeatherVariable.cloud_cover: ("cloud_cover_mean",),
    WeatherVariable.uv_index: ("uv_index_max",),
}

_DAILY_UNITS = {
    "temperature": "°C",
    "precipitation": "mm",
    "wind_speed": "km/h",
    "relative_humidity": "%",
    "shortwave_radiation": "MJ/m²",
}
_HOURLY_UNITS = {**_DAILY_UNITS, "shortwave_radiation": "W/m²"}

_Payload = dict[str, Any]
_CACHE: TTLCache[_Payload] = TTLCache()


def _selected(params: WeatherInput) -> list[WeatherVariable]:
    return list(params.variables) if params.variables else list(WeatherVariable)


def _cache_key(params: WeatherInput, selected: list[WeatherVariable]) -> str:
    return json.dumps(
        {
            "latitude": params.latitude,
            "longitude": params.longitude,
            "days": params.days,
            "granularity": params.granularity.value,
            "variables": [variable.value for variable in selected],
            "timezone": params.timezone,
        },
        sort_keys=True,
    )


async def _payload(
    params: WeatherInput,
    selected: list[WeatherVariable],
    key: str,
) -> CacheEntry[_Payload]:
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    request: dict[str, Any] = {
        "latitude": params.latitude,
        "longitude": params.longitude,
        "forecast_days": params.days,
        "timezone": params.timezone,
        "wind_speed_unit": "kmh",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
    }
    if params.granularity is Granularity.daily:
        request["daily"] = ",".join(
            output_key for variable in selected for output_key in _DAILY_KEYS[variable]
        )
    else:
        request["hourly"] = ",".join(variable.value for variable in selected)

    payload = _object(await get_json(FORECAST_URL, params=request))
    if payload is None:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Open-Meteo devolvió una respuesta no válida.",
        )
    return _CACHE.set(key, payload, _CACHE_TTL)


def _object(raw: Any) -> dict[str, Any] | None:
    return cast("dict[str, Any]", raw) if isinstance(raw, dict) else None


def _series(block: dict[str, Any], key: str) -> list[Any] | None:
    value = block.get(key)
    return cast("list[Any]", value) if isinstance(value, list) else None


def _value(raw: Any) -> float | int | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return raw
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _daily_points(block: dict[str, Any], keys: list[str]) -> list[WeatherPoint]:
    times = _series(block, "time")
    if times is None:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Open-Meteo devolvió una previsión diaria no válida.",
        )
    points: list[WeatherPoint] = []
    for index, time in enumerate(times):
        values: dict[str, float | int | None] = {}
        for key in keys:
            series = _series(block, key)
            raw = series[index] if series is not None and index < len(series) else None
            values[key] = _value(raw)
        points.append(WeatherPoint(time=str(time), values=values))
    return points


def _hourly_points(
    block: dict[str, Any],
    variables: list[WeatherVariable],
    timezone: str,
) -> list[WeatherPoint]:
    times = _series(block, "time")
    if times is None:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "Open-Meteo devolvió una previsión horaria no válida.",
        )
    zone = ZoneInfo(timezone)
    points: list[WeatherPoint] = []
    for index, time in enumerate(times):
        values: dict[str, float | int | None] = {}
        for variable in variables:
            series = _series(block, variable.value)
            raw = series[index] if series is not None and index < len(series) else None
            values[variable.value] = _value(raw)
        points.append(
            WeatherPoint(
                time=_local_timestamp(str(time), zone),
                values=values,
            )
        )
    return points


def _local_timestamp(value: str, zone: ZoneInfo) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.isoformat()


@tool(
    name="weather.forecast",
    version="1.0.0",
    title="Previsión meteorológica",
    permissions=["weather.read"],
    data_classification="public",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    open_world=True,
    mcp_description=(
        "Previsión meteorológica por coordenadas (1-7 días) con Open-Meteo. "
        "Admite granularidad diaria u horaria y devuelve unidades métricas."
    ),
)
async def forecast_weather(
    params: WeatherInput,
    ctx: ToolContext,
) -> ToolResult[WeatherOutput]:
    try:
        ZoneInfo(params.timezone)
    except ZoneInfoNotFoundError as error:
        raise ToolError(
            ErrorCode.INVALID_PARAMS,
            f"Zona horaria desconocida: {params.timezone}",
        ) from error

    selected = _selected(params)
    entry = await _payload(params, selected, _cache_key(params, selected))
    payload = entry.value

    if params.granularity is Granularity.daily:
        block = _object(payload.get("daily"))
        if block is None:
            raise ToolError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Open-Meteo no devolvió datos diarios.",
            )
        keys = [output_key for variable in selected for output_key in _DAILY_KEYS[variable]]
        points = _daily_points(block, keys)
    else:
        block = _object(payload.get("hourly"))
        if block is None:
            raise ToolError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Open-Meteo no devolvió datos horarios.",
            )
        points = _hourly_points(block, selected, params.timezone)

    location = Location(
        latitude=float(payload.get("latitude", params.latitude)),
        longitude=float(payload.get("longitude", params.longitude)),
        elevation=_optional_float(payload.get("elevation")),
        timezone=str(payload.get("timezone", params.timezone)),
    )

    return tool_result(
        WeatherOutput(
            location=location,
            granularity=params.granularity,
            points=points,
        ),
        metadata_extra={
            "source": "open_meteo",
            "source_type": "external_api",
            "source_url": _SOURCEFORECAST_URL,
            "retrieved_at": entry.retrieved_at,
            "valid_until": entry.valid_until,
            "result_type": "forecast",
            "is_estimated": True,
            "unit_system": "metric",
            "units": (_DAILY_UNITS if params.granularity is Granularity.daily else _HOURLY_UNITS),
            "timezone": params.timezone,
            "attribution": _ATTRIBUTION,
        },
    )


def _optional_float(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
