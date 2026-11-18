---
estado: v2
version: 0.1.0
tool: sim.solar_payback
---

# `sim.solar_payback` — Simulación de amortización solar

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `sim.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (modelo financiero) |
| Caché | n/a |
| Perfiles | `praxis-sim` |

## 2. Semántica exacta

Simula la rentabilidad de una instalación fotovoltaica de autoconsumo.

Por cada año `y` (1…`years`):

1. `generation_y = pv_kwp × specific_yield × (1 − degradation)^(y−1)`.
2. `self_consumed_y = min(generation_y × self_consumption_ratio, annual_consumption_kwh)`.
3. `exported_y = generation_y − self_consumed_y`.
4. `savings_y = self_consumed_y × electricity_price + exported_y × export_price`.
5. `cumulative_y = Σ savings`.

Resultados:

- `payback_years`: interpolación lineal del primer año en que `cumulative ≥ capex`.
- `npv`: `−capex + Σ savings_y / (1 + discount_rate)^y`.
- `lifetime_savings`: `cumulative` al final del horizonte.
- `co2_avoided_kg`: `self_consumed_1 × 0.15` (factor de red peninsular, orientativo).

Reglas:

- `annual_consumption_kwh > 0`, `pv_kwp > 0`, `capex > 0`, `electricity_price ≥ 0`.
- `self_consumption_ratio ∈ [0, 1]`; `export_price` por defecto `0`.
- `degradation_pct ∈ [0, 5]`; `years ∈ [1, 40]`; `discount_rate ∈ [0, 20]`.
- Si `exported_y = 0`, no hay ingreso por excedentes.
- `include_cashflows=true` añade la serie anual (año, generación, autoconsumo, excedentes, ahorro, acumulado).
- Importes 2 decimales; energía 2 decimales (kWh).
- `is_estimated=true`: no sustituye un estudio técnico ni la optimización fiscal.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class SolarPaybackInput(BaseModel):
    annual_consumption_kwh: Decimal = Field(gt=0)
    pv_kwp: Decimal = Field(gt=0)
    self_consumption_ratio: Decimal = Field(ge=0, le=1, default=0.6)
    specific_yield_kwh_per_kwp: Decimal = Field(gt=0, default=1400)
    capex: Decimal = Field(gt=0, decimal_places=2)
    electricity_price_eur_kwh: Decimal = Field(ge=0, decimal_places=5, default=0.25)
    export_price_eur_kwh: Decimal = Field(ge=0, decimal_places=5, default=0)
    degradation_pct: Decimal = Field(ge=0, le=5, default=0.5)
    years: int = Field(default=25, ge=1, le=40)
    discount_rate_pct: Decimal = Field(ge=0, le=20, default=3)
    include_cashflows: bool = False
    currency: str = "EUR"

class CashflowYear(BaseModel):
    year: int
    generation_kwh: Decimal
    self_consumed_kwh: Decimal
    exported_kwh: Decimal
    savings: Decimal
    cumulative: Decimal

class SolarPaybackOutput(BaseModel):
    annual_generation_kwh: Decimal
    self_consumed_kwh: Decimal
    exported_kwh: Decimal
    first_year_savings: Decimal
    payback_years: Decimal
    npv: Decimal
    lifetime_savings: Decimal
    co2_avoided_kg: Decimal
    cashflows: list[CashflowYear] | None
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | 8.000 kWh, 10 kWp, 60%, capex 12.000 € | payback 4,86 años, NPV 29.801,35 € |
| Excedentes a 0 € | `export_price=0` | solo ahorra el autoconsumo |
| Sin excedentes | `ratio` muy bajo | `exported=0` |
| Horizonte corto | `years=5` | NPV y ahorro a 5 años |
| Con desglose | `include_cashflows=true` | serie anual completa |
| Ratio inválido | `self_consumption_ratio=1.2` | error `invalid_params` |
| Capex cero | `capex=0` | error `invalid_params` |
| Años fuera de rango | `years=50` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "annual_consumption_kwh": "8000",
    "pv_kwp": "10",
    "self_consumption_ratio": "0.6",
    "specific_yield_kwh_per_kwp": "1400",
    "capex": "12000",
    "electricity_price_eur_kwh": "0.25",
    "export_price_eur_kwh": "0.08",
    "degradation_pct": "0.5",
    "years": 25,
    "discount_rate_pct": "3"
  },
  "output": {
    "annual_generation_kwh": "14000.00",
    "self_consumed_kwh": "8000.00",
    "exported_kwh": "6000.00",
    "first_year_savings": "2480.00",
    "payback_years": "4.86",
    "npv": "29801.35",
    "lifetime_savings": "59657.62",
    "co2_avoided_kg": "1200.00",
    "cashflows": null,
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "annual_consumption_kwh": "8000",
    "pv_kwp": "10",
    "capex": "12000",
    "include_cashflows": true
  },
  "output": {
    "cashflows": [
      { "year": 1, "generation_kwh": "14000.00", "self_consumed_kwh": "8000.00", "exported_kwh": "6000.00", "savings": "2000.00", "cumulative": "2000.00" },
      { "year": 2, "generation_kwh": "13930.00", "self_consumed_kwh": "8000.00", "exported_kwh": "5930.00", "savings": "2000.00", "cumulative": "4000.00" }
    ],
    "note": "Con export_price=0 por defecto; se muestran solo los dos primeros años"
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "simulation",
  "is_estimated": true,
  "currency": "EUR",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Usa `energy.pvpc_hourly` o `energy.tariff_simulator` para precios más realistas.
- Complementa `energy.self_consumption_payback` con serie temporal y NPV.
- Puede alimentar `finance.business_kpi` con ahorro energético anual.

## 8. Decisiones pendientes

- Pendiente: modelo horario con curva de consumo y precios PVPC; dataset.
- Pendiente: financiación, inflación de precios y fiscalidad (IVA, IBI, deducciones); validación legal.
- Pendiente: baterías y carga de vehículo eléctrico; decisión de producto.
- Pendiente: factor CO₂ por comercializadora y año; dataset.
