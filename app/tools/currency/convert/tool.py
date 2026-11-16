import csv
import io
from datetime import date as Date
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from app.clock import today as current_date
from app.context import ToolContext
from app.errors import ErrorCode, ToolError
from app.providers.cache import CacheEntry, TTLCache
from app.providers.http import get_text
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.currency.convert.schemas import (
    CurrencyConvertInput,
    CurrencyConvertOutput,
)

ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D..EUR.SP00.A"
_ATTRIBUTION = "Tipos de cambio de referencia del BCE"
_SOURCE_URL = "https://data-api.ecb.europa.eu"
_CACHE_TTL = timedelta(hours=12)
_RATE_QUANTUM = Decimal("0.000001")
_CENT = Decimal("0.01")
_SUPPORTED = frozenset(
    {
        "EUR",
        "USD",
        "JPY",
        "BGN",
        "CZK",
        "DKK",
        "GBP",
        "HUF",
        "PLN",
        "RON",
        "SEK",
        "CHF",
        "ISK",
        "NOK",
        "TRY",
        "AUD",
        "BRL",
        "CAD",
        "CNY",
        "HKD",
        "IDR",
        "ILS",
        "INR",
        "KRW",
        "MXN",
        "MYR",
        "NZD",
        "PHP",
        "SGD",
        "THB",
        "ZAR",
    }
)

_Rates = tuple[dict[str, Decimal], Date]
_CACHE: TTLCache[_Rates] = TTLCache()


def _parse_csv(payload: str) -> dict[Date, dict[str, Decimal]]:
    rates: dict[Date, dict[str, Decimal]] = {}
    for row in csv.DictReader(io.StringIO(payload)):
        period = row.get("TIME_PERIOD")
        currency = row.get("CURRENCY")
        observation = row.get("OBS_VALUE")
        if not period or not currency or not observation:
            continue
        try:
            rate = Decimal(observation)
        except InvalidOperation:
            continue
        rates.setdefault(Date.fromisoformat(period), {})[currency] = rate
    return rates


async def _rates_for(day: Date) -> CacheEntry[_Rates]:
    cached = _CACHE.get(day.isoformat())
    if cached is not None:
        return cached

    start = day - timedelta(days=14)
    payload = await get_text(
        ECB_URL,
        params={
            "format": "csvdata",
            "startPeriod": start.isoformat(),
            "endPeriod": day.isoformat(),
        },
    )
    rates_by_date = _parse_csv(payload)
    eligible = [period for period in rates_by_date if period <= day]
    if not eligible:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El BCE no publicó tipos de cambio para la fecha solicitada.",
        )
    effective = max(eligible)
    return _CACHE.set(day.isoformat(), (rates_by_date[effective], effective), _CACHE_TTL)


def _normalize(code: str) -> str:
    normalized = code.upper()
    if normalized not in _SUPPORTED:
        raise ToolError(
            "unsupported_currency",
            f"Divisa no soportada: {normalized}",
        )
    return normalized


def _rate_for(code: str, rates: dict[str, Decimal]) -> Decimal:
    if code == "EUR":
        return Decimal(1)
    rate = rates.get(code)
    if rate is None:
        raise ToolError(
            "unsupported_currency",
            f"El BCE no publica tipo de cambio para {code}.",
        )
    return rate


@tool(
    name="currency.convert",
    version="1.0.0",
    title="Convertir divisas",
    permissions=["currency.read"],
    data_classification="public",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    open_world=True,
    mcp_description=(
        "Convierte un importe entre divisas fiduciarias usando los tipos de referencia "
        "del BCE. Si la fecha cae en fin de semana o festivo, usa el último día hábil "
        "anterior y lo indica en `rate_date`."
    ),
)
async def convert_currency(
    params: CurrencyConvertInput,
    ctx: ToolContext,
) -> ToolResult[CurrencyConvertOutput]:
    from_code = _normalize(params.from_currency)
    to_code = _normalize(params.to_currency)

    if params.date is not None and params.date > current_date():
        raise ToolError(
            ErrorCode.INVALID_PARAMS,
            "No se pueden consultar tipos de cambio futuros.",
        )

    requested_day = params.date or current_date()
    entry = await _rates_for(requested_day)
    rates, effective = entry.value

    with localcontext() as context:
        context.prec = 50
        rate = (_rate_for(to_code, rates) / _rate_for(from_code, rates)).quantize(
            _RATE_QUANTUM, rounding=ROUND_HALF_UP
        )
        converted = (params.amount * rate).quantize(_CENT, rounding=ROUND_HALF_UP)
        amount = params.amount.quantize(_CENT, rounding=ROUND_HALF_UP)

    return tool_result(
        CurrencyConvertOutput(
            amount=amount,
            converted_amount=converted,
            rate=rate,
            rate_date=effective,
            from_currency=from_code,
            to_currency=to_code,
        ),
        metadata_extra={
            "source": "ecb",
            "source_type": "external_api",
            "source_url": _SOURCE_URL,
            "retrieved_at": entry.retrieved_at,
            "valid_until": entry.valid_until,
            "result_type": "conversion",
            "currency": to_code,
            "attribution": _ATTRIBUTION,
        },
    )
