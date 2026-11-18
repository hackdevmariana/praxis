---
estado: v2
version: 0.1.0
tool: energy.pvpc_hourly
---

# `energy.pvpc_hourly` — Precio horario PVPC

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `energy.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | ESIOS (REE), token por instalación |
| Caché | hasta la siguiente actualización del precio |
| Perfiles | `praxis-biz`, `praxis-sim` |

## 2. Semántica exacta

Devuelve el precio horario del PVPC para un día y zona.

- **Zonas:** `peninsula`, `canarias`, `baleares`, `ceuta`, `melilla`.
- **Componente:** `total` (por defecto) incluye energía, peajes y cargos; `energy` solo el coste de la energía.
- **Disponibilidad:** hoy y días pasados; mañana solo tras la publicación (~20:15). Más allá de mañana → `invalid_params`.
- **Fechas:** la zona horaria de referencia es `Europe/Madrid` (península, Baleares, Ceuta y Melilla) o `Atlantic/Canary` para Canarias; el campo `hour` es siempre 0–23 local.
- **Precios:** EUR/kWh con **5 decimales** (excepción documentada a la regla de 2 decimales para dinero, por la precisión del PVPC).
- **Provisional:** los precios de mañana pueden ser provisionales → `is_estimated=true` y warning `provisional_prices`.
- **Caché caducada:** si ESIOS no responde pero hay dato previo del mismo día, se sirve con warning `stale_data` y `retrieved_at` original; nunca se inventan precios.
- Si no hay dato para la fecha → `data_not_available`; si el proveedor falla sin caché → `provider_unavailable`.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel

class Zone(str, Enum):
    peninsula = "peninsula"
    canarias = "canarias"
    baleares = "baleares"
    ceuta = "ceuta"
    melilla = "melilla"

class Component(str, Enum):
    total = "total"
    energy = "energy"

class PvpcInput(BaseModel):
    date: date
    zone: Zone = Zone.peninsula
    component: Component = Component.total

class HourPrice(BaseModel):
    hour: int
    price_eur_kwh: Decimal

class PvpcOutput(BaseModel):
    date: date
    zone: Zone
    component: Component
    hours: list[HourPrice]
    min_price: Decimal
    min_hour: int
    max_price: Decimal
    max_hour: int
    avg_price: Decimal
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Día completo | `date=2026-11-13`, península, total | 24 precios, mín. 0.11200 (h3), máx. 0.28900 (h20), media 0.16667 |
| Solo energía | `component=energy` | precios menores que `total` |
| Canarias | `zone=canarias` | 24 precios, TZ `Atlantic/Canary` |
| Mañana provisional | fecha = mañana | `is_estimated=true`, warning |
| Fecha futura lejana | `date=hoy+3` | error `invalid_params` |
| Sin datos | día sin publicación | error `data_not_available` |
| ESIOS caído con caché | 5xx + dato del día | warning `stale_data` |
| ESIOS caído sin caché | 5xx | error `provider_unavailable` |

## 5. Golden cases

Fixture `esios-pvpc-2026-11-13-peninsula.json` (precios `total`).

```json
{
  "input": { "date": "2026-11-13", "zone": "peninsula", "component": "total" },
  "output": {
    "date": "2026-11-13",
    "zone": "peninsula",
    "component": "total",
    "hours": [
      { "hour": 0, "price_eur_kwh": "0.15100" },
      { "hour": 1, "price_eur_kwh": "0.14200" },
      { "hour": 2, "price_eur_kwh": "0.13100" },
      { "hour": 3, "price_eur_kwh": "0.11200" },
      { "hour": 4, "price_eur_kwh": "0.11500" },
      { "hour": 5, "price_eur_kwh": "0.11800" },
      { "hour": 6, "price_eur_kwh": "0.12100" },
      { "hour": 7, "price_eur_kwh": "0.14500" },
      { "hour": 8, "price_eur_kwh": "0.16200" },
      { "hour": 9, "price_eur_kwh": "0.15800" },
      { "hour": 10, "price_eur_kwh": "0.14900" },
      { "hour": 11, "price_eur_kwh": "0.14400" },
      { "hour": 12, "price_eur_kwh": "0.13900" },
      { "hour": 13, "price_eur_kwh": "0.13500" },
      { "hour": 14, "price_eur_kwh": "0.14100" },
      { "hour": 15, "price_eur_kwh": "0.15600" },
      { "hour": 16, "price_eur_kwh": "0.17400" },
      { "hour": 17, "price_eur_kwh": "0.19800" },
      { "hour": 18, "price_eur_kwh": "0.23100" },
      { "hour": 19, "price_eur_kwh": "0.26700" },
      { "hour": 20, "price_eur_kwh": "0.28900" },
      { "hour": 21, "price_eur_kwh": "0.25400" },
      { "hour": 22, "price_eur_kwh": "0.20100" },
      { "hour": 23, "price_eur_kwh": "0.16800" }
    ],
    "min_price": "0.11200",
    "min_hour": 3,
    "max_price": "0.28900",
    "max_hour": 20,
    "avg_price": "0.16667"
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "esios",
  "source_type": "external_api",
  "retrieved_at": "<now>",
  "valid_until": "2026-11-14T00:00:00+01:00",
  "result_type": "time_series",
  "is_estimated": false,
  "currency": "EUR",
  "unit": "EUR/kWh",
  "timezone": "Europe/Madrid",
  "attribution": "ESIOS / Red Eléctrica de España",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Base de `energy.cheapest_hours` y `energy.tariff_simulator`.
- Alimenta `energy.autoconsumption_payback` con el precio de la electricidad.
- Usada por `alerts.*` para avisar de picos de precio (v2).

## 8. Decisiones pendientes

- Pendiente: token ESIOS: alta por email y almacenamiento cifrado por instalación; requiere API.
- Pendiente: mercados OMIE además de PVPC (`energy.omie` en v2); requiere API.
- Pendiente: confirmar tratamiento de festivos y cambios de hora (23/25 horas) en la serie; dataset.
