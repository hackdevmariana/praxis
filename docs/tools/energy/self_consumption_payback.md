---
estado: v2
version: 0.1.0
tool: energy.self_consumption_payback
---

# `energy.self_consumption_payback` — Rentabilidad de autoconsumo

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `energy.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (datos aportados por el usuario) |
| Caché | n/a |
| Perfiles | `praxis-biz`, `praxis-sim` |

## 2. Semántica exacta

Calcula el ahorro y la rentabilidad de una instalación fotovoltaica de autoconsumo.

Por cada año `y = 1..years`:

1. `production_y = round(annual_production_kwh × (1 − degradation_pct/100)^(y−1), 2)`.
2. `self_consumed_y = round(production_y × self_consumption_pct/100, 2)`.
3. `exported_y = production_y − self_consumed_y`.
4. `savings_y = round(self_consumed_y × electricity_price + exported_y × export_price − annual_opex, 2)`.
5. `net_cashflow_y = savings_y` (no hay inversión recurrente).

`annual_opex` es **constante** (no se degrada); la degradación solo afecta a la producción.

Indicadores:

- `year1_savings`: ahorro del primer año.
- `simple_payback_years = capex / year1_savings` (si `year1_savings ≤ 0` → `null`).
- `payback_years`: año (interpolado) en que la suma acumulada de `savings_y` cubre `capex`; `null` si no se recupera en `years`.
- `npv = −capex + Σ savings_y / (1 + discount_rate/100)^y`.
- `irr_pct`: TIR de los flujos `[−capex, savings_1..savings_n]`; `null` si no hay cambio de signo.

Reglas:

- `installation_kwp > 0`, `annual_production_kwh > 0`, `self_consumption_pct ∈ [0, 100]`.
- `capex ≥ 0`; precios y `annual_opex ≥ 0`; `degradation_pct ∈ [0, 10]`.
- `years ∈ [1, 40]`; `discount_rate_pct ∈ [0, 30]`.
- No se incluyen impuestos, subvenciones ni IVA; si aplican, se ajusta `capex` antes de llamar o se usa una tool fiscal aparte.
- Importes en EUR con 2 decimales; años con 2 decimales; porcentajes con 2.
- `is_estimated=true`: depende de la producción y el perfil aportados.
- No se asume autoconsumo instantáneo perfecto: el `self_consumption_pct` lo aporta el usuario (o una simulación horaria en v3).

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class SelfConsumptionInput(BaseModel):
    installation_kwp: Decimal = Field(gt=0)
    annual_production_kwh: Decimal = Field(gt=0)
    self_consumption_pct: Decimal = Field(ge=0, le=100)
    capex: Decimal = Field(ge=0, decimal_places=2)
    electricity_price_eur_kwh: Decimal = Field(ge=0)
    export_price_eur_kwh: Decimal = Field(default=Decimal("0"), ge=0)
    annual_opex: Decimal = Field(default=Decimal("0"), ge=0)
    degradation_pct: Decimal = Field(default=Decimal("0.5"), ge=0, le=10)
    years: int = Field(default=25, ge=1, le=40)
    discount_rate_pct: Decimal = Field(default=Decimal("3"), ge=0, le=30)
    currency: str = "EUR"

class CashflowYear(BaseModel):
    year: int
    production_kwh: Decimal
    self_consumed_kwh: Decimal
    exported_kwh: Decimal
    savings: Decimal
    cumulative_savings: Decimal

class SelfConsumptionOutput(BaseModel):
    year1_savings: Decimal
    simple_payback_years: Decimal | None
    payback_years: Decimal | None
    npv: Decimal
    irr_pct: Decimal | None
    cashflows: list[CashflowYear]
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | 5 kWp, 7000 kWh, 60% auto, capex 5000, 0.18/0.06 | año1 874.00, payback simple 5.72, TIR 16.62% |
| Sin excedentes | `export_price=0` | ahorro menor |
| Autoconsumo 100% | `self_consumption_pct=100` | sin excedentes |
| Sin autoconsumo | `self_consumption_pct=0` | solo ingresos por excedentes |
| Ahorro negativo | `annual_opex` alto | payback `null` |
| Años insuficientes | `years=5` | payback `null` |
| Capex cero | `capex=0` | payback 0, NPV positivo |
| Parámetros inválidos | `self_consumption_pct=101` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "installation_kwp": "5",
    "annual_production_kwh": "7000",
    "self_consumption_pct": "60",
    "capex": "5000",
    "electricity_price_eur_kwh": "0.18",
    "export_price_eur_kwh": "0.06",
    "annual_opex": "50",
    "degradation_pct": "0.5",
    "years": 25,
    "discount_rate_pct": "3"
  },
  "output": {
    "year1_savings": "874.00",
    "simple_payback_years": "5.72",
    "payback_years": "5.79",
    "npv": "9405.61",
    "irr_pct": "16.62",
    "cashflows": [
      { "year": 1, "production_kwh": "7000.00", "self_consumed_kwh": "4200.00", "exported_kwh": "2800.00", "savings": "874.00", "cumulative_savings": "874.00" },
      { "year": 2, "production_kwh": "6965.00", "self_consumed_kwh": "4179.00", "exported_kwh": "2786.00", "savings": "869.38", "cumulative_savings": "1743.38" },
      { "year": 3, "production_kwh": "6930.18", "self_consumed_kwh": "4158.11", "exported_kwh": "2772.07", "savings": "864.78", "cumulative_savings": "2608.16" },
      { "year": 4, "production_kwh": "6895.52", "self_consumed_kwh": "4137.31", "exported_kwh": "2758.21", "savings": "860.21", "cumulative_savings": "3468.37" },
      { "year": 5, "production_kwh": "6861.05", "self_consumed_kwh": "4116.63", "exported_kwh": "2744.42", "savings": "855.66", "cumulative_savings": "4324.03" },
      { "year": 6, "production_kwh": "6826.74", "self_consumed_kwh": "4096.04", "exported_kwh": "2730.70", "savings": "851.13", "cumulative_savings": "5175.16" }
    ],
    "currency": "EUR"
  },
  "note": "cashflows del golden completo tienen 25 filas; aquí se muestran las 6 primeras"
}
```

```json
{
  "input": {
    "installation_kwp": "5",
    "annual_production_kwh": "7000",
    "self_consumption_pct": "60",
    "capex": "5000",
    "electricity_price_eur_kwh": "0.18",
    "export_price_eur_kwh": "0.06",
    "annual_opex": "1000",
    "years": 25
  },
  "output": {
    "year1_savings": "-76.00",
    "simple_payback_years": null,
    "payback_years": null,
    "irr_pct": null
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
  "confidence": 0.75,
  "currency": "EUR",
  "unit": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa `energy.pvpc_hourly` / `energy.tariff_simulator` para fijar `electricity_price_eur_kwh`.
- Alimenta `sim.solar_payback` con una simulación horaria y datos PVGIS.
- Combinable con `finance.loan_schedule` si la inversión se financia.

## 8. Decisiones pendientes

- Pendiente: modelo horario de autoconsumo con curva de consumo y producción (v3); dataset.
- Pendiente: subvenciones (BDNS) y deducciones fiscales (IRPF/IS) como ajustes de `capex`; validación legal.
- Pendiente: precios de la energía crecientes (`price_escalation_pct`); decisión de producto.
- Pendiente: coste de mantenimiento creciente y seguro; decisión de producto.
