---
estado: v2
version: 0.1.0
tool: energy.cheapest_hours
---

# `energy.cheapest_hours` — Horas más baratas

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `energy.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | ESIOS (vía `energy.pvpc_hourly`) |
| Caché | heredada de `energy.pvpc_hourly` |
| Perfiles | `praxis-biz`, `praxis-sim` |

## 2. Semántica exacta

Selecciona las `hours_needed` horas más baratas de un día según PVPC.

- `contiguous=true` (por defecto): busca la **ventana contigua** de `hours_needed` horas con menor precio medio (deslizante; empate → la más temprana).
- `contiguous=false`: elige las `hours_needed` horas individuales más baratas y las devuelve ordenadas cronológicamente.
- `start_hour` es inclusivo y `end_hour` exclusivo (ventana de 4 horas que empieza a las 03:00 → `start_hour=3`, `end_hour=7`).
- `estimated_cost` se calcula si se aporta `consumption_kwh`, repartiendo el consumo **uniformemente** entre las horas seleccionadas: `cost = consumption_kwh × avg_price`.
- Los precios son EUR/kWh con 5 decimales; `estimated_cost` en EUR con 2 decimales.
- Acepta `component` y `zone` de `energy.pvpc_hourly`.
- Fechas sin datos o proveedor caído → mismos errores que `energy.pvpc_hourly`.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

class CheapestHoursInput(BaseModel):
    date: date
    hours_needed: int = Field(ge=1, le=24)
    zone: str = "peninsula"
    component: str = "total"
    contiguous: bool = True
    consumption_kwh: Decimal | None = Field(default=None, gt=0)

class SelectedHour(BaseModel):
    hour: int
    price_eur_kwh: Decimal

class CheapestHoursOutput(BaseModel):
    date: date
    hours_needed: int
    contiguous: bool
    start_hour: int
    end_hour: int
    selected_hours: list[SelectedHour]
    avg_price: Decimal
    max_price: Decimal
    estimated_cost: Decimal | None
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Ventana de 4h | `hours_needed=4`, `contiguous=true` | 03:00–07:00, media 0.11650 |
| 4h sueltas | `contiguous=false` | mismas horas en este fixture |
| Ventana de 6h | `hours_needed=6`, contigua | 01:00–07:00, media 0.12317 |
| 6h sueltas | `contiguous=false` | h2,3,4,5,6,13, media 0.12200 |
| Coste con consumo | 4h + `consumption_kwh=10` | 1.17 EUR |
| Día completo | `hours_needed=24` | 24 horas, media 0.16667 |
| Fuera de rango | `hours_needed=25` | error `invalid_params` |
| Sin datos | fecha sin PVPC | error `data_not_available` |

## 5. Golden cases

```json
{
  "input": { "date": "2026-11-13", "hours_needed": 4, "contiguous": true, "consumption_kwh": "10" },
  "output": {
    "date": "2026-11-13",
    "hours_needed": 4,
    "contiguous": true,
    "start_hour": 3,
    "end_hour": 7,
    "selected_hours": [
      { "hour": 3, "price_eur_kwh": "0.11200" },
      { "hour": 4, "price_eur_kwh": "0.11500" },
      { "hour": 5, "price_eur_kwh": "0.11800" },
      { "hour": 6, "price_eur_kwh": "0.12100" }
    ],
    "avg_price": "0.11650",
    "max_price": "0.12100",
    "estimated_cost": "1.17"
  }
}
```

```json
{
  "input": { "date": "2026-11-13", "hours_needed": 6, "contiguous": true },
  "output": {
    "start_hour": 1,
    "end_hour": 7,
    "selected_hours": [
      { "hour": 1, "price_eur_kwh": "0.14200" },
      { "hour": 2, "price_eur_kwh": "0.13100" },
      { "hour": 3, "price_eur_kwh": "0.11200" },
      { "hour": 4, "price_eur_kwh": "0.11500" },
      { "hour": 5, "price_eur_kwh": "0.11800" },
      { "hour": 6, "price_eur_kwh": "0.12100" }
    ],
    "avg_price": "0.12317",
    "max_price": "0.14200",
    "estimated_cost": null
  }
}
```

```json
{
  "input": { "date": "2026-11-13", "hours_needed": 6, "contiguous": false },
  "output": {
    "selected_hours": [
      { "hour": 2, "price_eur_kwh": "0.13100" },
      { "hour": 3, "price_eur_kwh": "0.11200" },
      { "hour": 4, "price_eur_kwh": "0.11500" },
      { "hour": 5, "price_eur_kwh": "0.11800" },
      { "hour": 6, "price_eur_kwh": "0.12100" },
      { "hour": 13, "price_eur_kwh": "0.13500" }
    ],
    "avg_price": "0.12200",
    "max_price": "0.13500"
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
  "result_type": "calculation",
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

- Usa `energy.pvpc_hourly`.
- Alimenta recomendaciones de carga (vehículo eléctrico, lavadoras, bombas de calor) y `energy.tariff_simulator`.
- `energy.self_consumption_payback` puede usar el precio medio de las horas seleccionadas.

## 8. Decisiones pendientes

- Permitir ventanas de varias horas no contiguas agrupadas en bloques ("2 bloques de 2h").
- Consumo no uniforme por hora (perfil horario del local) en v1.1.
- Restricciones ("no antes de las 08:00", "máximo 2 bloques").
