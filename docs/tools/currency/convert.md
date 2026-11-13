---
estado: MVP
version: 1.0.0
tool: currency.convert
---

# `currency.convert` — Conversión de divisas

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `currency.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true (para una `date` dada) |
| requires_confirmation | false |
| Provider | BCE (`ecb`) |
| Caché | 12 h por fecha de referencia |
| Perfiles | all |

## 2. Semántica exacta

Convierte un importe entre divisas usando los tipos de referencia del BCE.

1. **Fecha de tipo:** si `date` se omite, se usa la última publicación disponible (hoy o el día hábil anterior). Si `date` cae en fin de semana o festivo del BCE, se usa el último día hábil anterior y se informa en `rate_date`.
2. **Ruta:** si ambas divisas tienen tipo EUR, se calcula la tasa cruzada `rate = rate_to / rate_from`.
3. **`rate`:** unidades de `to_currency` por 1 `from_currency`, con 6 decimales (`ROUND_HALF_UP`).
4. **`converted_amount`:** `round(amount × rate, 2)`.
5. **Misma divisa:** `rate = 1`, `converted_amount = amount`, `rate_date = date` (o la última disponible).
6. **Divisa no soportada** (p. ej. `BTC`, `ETH`): error `unsupported_currency`; no se estima.
7. **Fecha futura:** error `invalid_params` (no se inventan tipos futuros).

Reglas:

- Códigos ISO 4217 en mayúsculas; se normalizan a mayúsculas antes de validar.
- `amount` admite `0`; no admite negativos (para restas, el llamador compone).
- El BCE publica referencia ~16:00 CET en días hábiles; `rate_date` refleja la fecha efectiva del dato.
- Importes como **string decimal** en JSON.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

class CurrencyConvertInput(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    date: date | None = None

class CurrencyConvertOutput(BaseModel):
    amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    rate_date: date
    from_currency: str
    to_currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| EUR→USD | `amount=100`, `from=EUR`, `to=USD`, `date=2026-11-13` | 108.50, rate 1.085000, rate_date 2026-11-13 |
| USD→EUR | `amount=100`, `from=USD`, `to=EUR`, `2026-11-13` | 92.17, rate 0.921659 |
| Cruzada USD→GBP | `amount=100`, `from=USD`, `to=GBP`, `2026-11-13` | 79.72, rate 0.797235 |
| Misma divisa | `from=EUR`, `to=EUR`, `amount=100` | 100.00, rate 1.000000 |
| Fin de semana | `date=2026-11-14` (sábado) | usa `rate_date=2026-11-13` |
| Cero | `amount=0` | 0.00 |
| Cripto | `to=BTC` | error `unsupported_currency` |
| Divisa inexistente | `to=XXX` | error `unsupported_currency` |
| Fecha futura | `date=2027-01-01` | error `invalid_params` |
| Minúsculas | `from=eur` | se normaliza a `EUR` |

## 5. Golden cases

Fixture congelado `ecb-2026-11-13.json` (para tests): `EUR/USD 1.0850`, `EUR/GBP 0.8650`, `EUR/JPY 163.20`.

```json
{
  "input": { "amount": "100", "from_currency": "EUR", "to_currency": "USD", "date": "2026-11-13" },
  "output": {
    "amount": "100.00",
    "converted_amount": "108.50",
    "rate": "1.085000",
    "rate_date": "2026-11-13",
    "from_currency": "EUR",
    "to_currency": "USD"
  }
}
```

```json
{
  "input": { "amount": "100", "from_currency": "USD", "to_currency": "EUR", "date": "2026-11-13" },
  "output": {
    "amount": "100.00",
    "converted_amount": "92.17",
    "rate": "0.921659",
    "rate_date": "2026-11-13",
    "from_currency": "USD",
    "to_currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "100", "from_currency": "USD", "to_currency": "GBP", "date": "2026-11-13" },
  "output": {
    "amount": "100.00",
    "converted_amount": "79.72",
    "rate": "0.797235",
    "rate_date": "2026-11-13",
    "from_currency": "USD",
    "to_currency": "GBP"
  }
}
```

```json
{
  "input": { "amount": "250", "from_currency": "EUR", "to_currency": "EUR", "date": "2026-11-14" },
  "output": {
    "amount": "250.00",
    "converted_amount": "250.00",
    "rate": "1.000000",
    "rate_date": "2026-11-13",
    "from_currency": "EUR",
    "to_currency": "EUR"
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "ecb",
  "source_type": "external_api",
  "source_url": "https://data-api.ecb.europa.eu",
  "retrieved_at": "<now>",
  "valid_until": "<retrieved_at + 12h>",
  "result_type": "conversion",
  "is_estimated": false,
  "currency": "USD",
  "attribution": "Tipos de cambio de referencia del BCE",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Usada por `procurement.compare_offers` para ofertas en divisas distintas.
- Usada por `documents.extract_invoice` cuando la factura no está en EUR.
- Base de `finance.kpi` (v2) para consolidar importes multi-divisa.

## 8. Decisiones pendientes

- Decimales por divisa (JPY 0, BHD 3): v1 usa 2 decimales; propuesta de `minor_units` en v1.1.
- ¿Añadir `inverse_rate` en la salida? Propuesta: sí, opcional.
- Criptomonedas: fuera de v1; proveedor específico y disclaimer en v2.
