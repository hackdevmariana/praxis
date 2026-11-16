import json
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal, cast

from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.cache import CacheEntry, TTLCache
from app.providers.http import get_json
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.geo.geocode.schemas import GeocodeInput, GeocodeOutput, GeocodeResult

CARTO_BASE = "https://www.cartociudad.es/geocoder/api/geocoder"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
_CACHE_TTL = timedelta(days=7)
_COORDINATE = Decimal("0.000001")
_CONFIDENCE = Decimal("0.01")
_INVALID_INPUT = re.compile(r"^\d{5}$")
_NOMINATIM_HEADERS = {"User-Agent": "PRAXIS/0.1 (geocoding fallback)"}

_ATTRIBUTIONS = {
    "cartociudad": "Geocodificación: CartoCiudad (IGN)",
    "nominatim": "Geocodificación: OpenStreetMap Nominatim",
}
_SOURCE_URLS = {
    "cartociudad": CARTO_BASE,
    "nominatim": NOMINATIM_BASE,
}

_Mode = Literal["forward", "reverse"]


@dataclass(frozen=True, slots=True)
class _GeoPayload:
    results: list[GeocodeResult]
    source: str
    warnings: list[str]


_CACHE: TTLCache[_GeoPayload] = TTLCache()


def _cache_key(params: GeocodeInput, mode: _Mode, ctx: ToolContext) -> str:
    return json.dumps(
        {
            "mode": mode,
            "address": params.address,
            "latitude": params.latitude,
            "longitude": params.longitude,
            "municipality_code": params.municipality_code,
            "limit": params.limit,
            "company_id": ctx.company_id,
        },
        sort_keys=True,
    )


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = cast("list[Any]", payload)
        return [cast("dict[str, Any]", item) for item in items if isinstance(item, dict)]
    if isinstance(payload, dict):
        mapping = cast("dict[str, Any]", payload)
        for key in ("results", "candidates", "addresses", "features"):
            value = mapping.get(key)
            if isinstance(value, list):
                nested = cast("list[Any]", value)
                return [cast("dict[str, Any]", item) for item in nested if isinstance(item, dict)]
        return [mapping]
    return []


def _text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _number(item: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _address_part(item: dict[str, Any], *keys: str) -> str | None:
    address = item.get("address")
    if not isinstance(address, dict):
        return None
    return _text(cast("dict[str, Any]", address), *keys)


def _ine_code(item: dict[str, Any]) -> str | None:
    value = _text(
        item,
        "ine_code",
        "codigo_ine",
        "codigoIne",
        "ine",
        "muniCode",
        "municipio_code",
    )
    if value is not None and _INVALID_INPUT.fullmatch(value):
        return value
    return None


def _coordinate(value: float) -> float:
    return float(Decimal(str(value)).quantize(_COORDINATE, rounding=ROUND_HALF_UP))


def _confidence(item: dict[str, Any]) -> float:
    value = _number(item, "confianza", "confidence", "importance", "score")
    if value is None:
        match _text(item, "type"):
            case "portal" if _text(item, "refCatastral"):
                value = 0.98
            case "portal":
                value = 0.95
            case "callejero":
                value = 0.9
            case _:
                value = 0.5
    if value > 1:
        value /= 100
    return float(
        Decimal(str(min(max(value, 0.0), 1.0))).quantize(
            _CONFIDENCE,
            rounding=ROUND_HALF_UP,
        )
    )


def _parse(
    payload: Any,
    source: str,
    params: GeocodeInput,
) -> list[GeocodeResult]:
    results: list[GeocodeResult] = []
    for item in _items(payload):
        latitude = _number(item, "lat", "latitude")
        longitude = _number(item, "lon", "lng", "longitude")
        if latitude is None or longitude is None:
            continue

        municipality = _text(
            item,
            "muni",
            "municipio",
            "municipality",
            "city",
            "town",
            "village",
            "poblacion",
        ) or _address_part(item, "city", "town", "village", "municipality")
        province = _text(item, "provincia", "province", "state") or _address_part(
            item,
            "state",
            "province",
        )
        postal_code = _text(
            item,
            "postalCode",
            "codPostal",
            "postal_code",
            "postcode",
        ) or _address_part(item, "postcode")

        results.append(
            GeocodeResult(
                latitude=_coordinate(latitude),
                longitude=_coordinate(longitude),
                normalized_address=_text(
                    item,
                    "address",
                    "normalized_address",
                    "display_name",
                    "label",
                )
                or f"{_coordinate(latitude)}, {_coordinate(longitude)}",
                ine_code=_ine_code(item),
                municipality=municipality,
                province=province,
                postal_code=postal_code,
                confidence=_confidence(item),
                source=source,
            )
        )

    if params.municipality_code:
        results = [
            result
            for result in results
            if result.ine_code is None or result.ine_code == params.municipality_code
        ]

    return results[: params.limit] if params.address is not None else results[:1]


async def _fetch(
    params: GeocodeInput,
    mode: _Mode,
    key: str,
) -> CacheEntry[_GeoPayload]:
    warnings: list[str] = []
    if mode == "forward":
        primary_url = f"{CARTO_BASE}/candidates"
        request_limit = 5 if params.municipality_code else params.limit
        primary_params: dict[str, Any] = {
            "q": params.address,
            "limit": request_limit,
        }
        if params.municipality_code:
            primary_params["municipio"] = params.municipality_code
        fallback_url = f"{NOMINATIM_BASE}/search"
        fallback_params: dict[str, Any] = {
            "q": params.address,
            "format": "jsonv2",
            "limit": request_limit,
            "addressdetails": 1,
        }
    else:
        primary_url = f"{CARTO_BASE}/reverseGeocode"
        primary_params = {"lat": params.latitude, "lon": params.longitude}
        fallback_url = f"{NOMINATIM_BASE}/reverse"
        fallback_params = {
            "lat": params.latitude,
            "lon": params.longitude,
            "format": "jsonv2",
            "addressdetails": 1,
        }

    try:
        payload = await get_json(primary_url, params=primary_params)
        source = "cartociudad"
    except ToolError as primary_error:
        try:
            payload = await get_json(
                fallback_url,
                params=fallback_params,
                headers=_NOMINATIM_HEADERS,
            )
            source = "nominatim"
            warnings.append("fallback_source_used")
        except ToolError as fallback_error:
            raise ToolError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Ningún proveedor de geocodificación respondió.",
                details={
                    "primary": primary_error.to_dict(),
                    "fallback": fallback_error.to_dict(),
                },
            ) from fallback_error

    results = _parse(payload, source, params)
    if not results:
        warnings.append("no_results")

    return _CACHE.set(
        key,
        _GeoPayload(results=results, source=source, warnings=warnings),
        _CACHE_TTL,
    )


@tool(
    name="geo.geocode",
    version="1.0.0",
    title="Geocodificar direcciones",
    permissions=["geo.read"],
    data_classification="public",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    open_world=True,
    mcp_description=(
        "Convierte direcciones en coordenadas (forward) o coordenadas en direcciones "
        "(reverse). Usa CartoCiudad y, si falla, Nominatim como fallback."
    ),
)
async def geocode(
    params: GeocodeInput,
    ctx: ToolContext,
) -> ToolResult[GeocodeOutput]:
    mode: _Mode = "forward" if params.address is not None else "reverse"
    key = _cache_key(params, mode, ctx)
    cached = _CACHE.get(key)
    entry = cached if cached is not None else await _fetch(params, mode, key)
    payload = entry.value

    confidence = max(
        (result.confidence for result in payload.results),
        default=None,
    )

    return tool_result(
        GeocodeOutput(mode=mode, results=payload.results),
        warnings=payload.warnings,
        metadata_extra={
            "source": payload.source,
            "source_type": "external_api",
            "source_url": _SOURCE_URLS[payload.source],
            "retrieved_at": entry.retrieved_at,
            "valid_until": entry.valid_until,
            "result_type": "geocoding",
            "is_estimated": False,
            "confidence": confidence,
            "timezone": "Europe/Madrid",
            "attribution": _ATTRIBUTIONS[payload.source],
        },
    )
