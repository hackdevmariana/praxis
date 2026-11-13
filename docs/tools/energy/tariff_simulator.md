---
estado: v2
version: 0.1.0
tool: energy.tariff_simulator
---

# `energy.tariff_simulator` — Simulador de tarifas eléctricas

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `energy.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (tarifas aportadas por el usuario) |
| Caché | n/a |
| Perfiles | `praxis-biz`, `praxis-sim` |

## 2. Semántica exacta

Compara el coste anual de 2–5 tarifas eléctricas con el mismo perfil de consumo.

1. **Reparto:** `peak_kwh = annual_consumption_kwh × peak_share_pct / 100`; `valley_kwh = consumo − peak_kwh`.
2. **Término de potencia:** `power_cost = power_price_eur_kw_year × contracted_power_kw`.
3. **Término de energía:** `energy_cost = peak_kwh × energy_price_peak + valley_kwh × energy_price_valley`.
4. **Término fijo:** `standing_cost = standing_charge_eur_month × 12`.
5. **Total:** `annual_cost = power_cost + energy_cost + standing_cost`; `monthly_avg = round(annual_cost / 12)`.
6. **Ranking:** orden ascendente por `annual_cost`; empate → nombre ascendente. `savings_vs_most_expensive = max(total) − total`.
7. `savings_pct` de la mejor tarifa: `(max − min) / max × 100`.

Reglas:

- `annual_consumption_kwh ≥ 0`; `peak_share_pct ∈ [0, 100]`.
- `contracted_power_kw > 0`.
- `tariffs` entre 2 y 5; nombres únicos.
- Precios `≥ 0`; importes `Decimal` con 2 decimales (precios de energía pueden llevar 5 decimales y se conservan en el cálculo).
- No se modelan impuestos (IVA, impuesto eléctrico) ni excedentes: se comparan costes **antes de impuestos**. Si se necesita, aplicar `finance.vat` después.
- `is_estimated=true`: depende de la exactitud del perfil aportado.
- No se valida que la tarifa exista comercialmente; solo se calculan los números aportados.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

class TariffInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    power_price_eur_kw_year: Decimal = Field(ge=0)
    energy_price_peak_eur_kwh: Decimal = Field(ge=0)
    energy_price_valley_eur_kwh: Decimal = Field(ge=0)
    standing_charge_eur_month: Decimal = Field(default=Decimal("0"), ge=0)

class TariffSimulatorInput(BaseModel):
    annual_consumption_kwh: Decimal = Field(ge=0)
    peak_share_pct: Decimal = Field(default=Decimal("40"), ge=0, le=100)
    contracted_power_kw: Decimal = Field(gt=0)
    tariffs: list[TariffInput] = Field(min_length=2, max_length=5)

    @field_validator("tariffs")
    @classmethod
    def nombres_unicos(cls, v):
        if len({t.name for t in v}) != len(v):
            raise ValueError("Los nombres de tarifa deben ser únicos")
        return v

class TariffResult(BaseModel):
    name: str
    peak_kwh: Decimal
    valley_kwh: Decimal
    power_cost: Decimal
    energy_cost: Decimal
    standing_cost: Decimal
    annual_cost: Decimal
    monthly_avg: Decimal
    rank: int
    savings_vs_most_expensive: Decimal
    is_cheapest: bool

class TariffSimulatorOutput(BaseModel):
    annual_consumption_kwh: Decimal
    peak_kwh: Decimal
    valley_kwh: Decimal
    currency: str
    ranking: list[TariffResult]
    savings_pct_best: Decimal | None
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Dos tarifas | 3500 kWh, 40% punta, 4.6 kW | A 810.00, B 715.00; ahorro 95.00 (11.73%) |
| Todo valle | `peak_share_pct=0` | solo se aplica precio valle |
| Todo punta | `peak_share_pct=100` | solo se aplica precio punta |
| Consumo cero | `annual_consumption_kwh=0` | solo potencia + fijo |
| Tarifas empatadas | dos tarifas iguales | empate resuelto por nombre |
| Una tarifa | `tariffs` con 1 | error `invalid_params` |
| Nombre duplicado | dos "A" | error `invalid_params` |
| Potencia cero | `contracted_power_kw=0` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "annual_consumption_kwh": "3500",
    "peak_share_pct": "40",
    "contracted_power_kw": "4.6",
    "tariffs": [
      { "name": "A", "power_price_eur_kw_year": "40", "energy_price_peak_eur_kwh": "0.22", "energy_price_valley_eur_kwh": "0.14", "standing_charge_eur_month": "2" },
      { "name": "B", "power_price_eur_kw_year": "35", "energy_price_peak_eur_kwh": "0.19", "energy_price_valley_eur_kwh": "0.12", "standing_charge_eur_month": "3" }
    ]
  },
  "output": {
    "annual_consumption_kwh": "3500.00",
    "peak_kwh": "1400.00",
    "valley_kwh": "2100.00",
    "currency": "EUR",
    "savings_pct_best": "11.73",
    "ranking": [
      {
        "name": "B",
        "peak_kwh": "1400.00",
        "valley_kwh": "2100.00",
        "power_cost": "161.00",
        "energy_cost": "518.00",
        "standing_cost": "36.00",
        "annual_cost": "715.00",
        "monthly_avg": "59.58",
        "rank": 1,
        "savings_vs_most_expensive": "95.00",
        "is_cheapest": true
      },
      {
        "name": "A",
        "peak_kwh": "1400.00",
        "valley_kwh": "2100.00",
        "power_cost": "184.00",
        "energy_cost": "602.00",
        "standing_cost": "24.00",
        "annual_cost": "810.00",
        "monthly_avg": "67.50",
        "rank": 2,
        "savings_vs_most_expensive": "0.00",
        "is_cheapest": false
      }
    ]
  }
}
```

```json
{
  "input": {
    "annual_consumption_kwh": "0",
    "contracted_power_kw": "4.6",
    "tariffs": [
      { "name": "A", "power_price_eur_kw_year": "40", "energy_price_peak_eur_kwh": "0.22", "energy_price_valley_eur_kwh": "0.14", "standing_charge_eur_month": "2" },
      { "name": "B", "power_price_eur_kw_year": "35", "energy_price_peak_eur_kwh": "0.19", "energy_price_valley_eur_kwh": "0.12", "standing_charge_eur_month": "3" }
    ]
  },
  "output": {
    "peak_kwh": "0.00",
    "valley_kwh": "0.00",
    "ranking": [
      { "name": "B", "annual_cost": "197.00", "rank": 1, "is_cheapest": true },
      { "name": "A", "annual_cost": "208.00", "rank": 2, "is_cheapest": false }
    ]
  },
  "note": "A: 184 + 24 = 208; B: 161 + 36 = 197. En este caso la mejor es B"
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "user_input",
  "source_type": "user_input",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "comparison",
  "is_estimated": true,
  "confidence": 0.8,
  "currency": "EUR",
  "unit": "EUR/year",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Puede usar los precios de `energy.pvpc_hourly` para estimar el coste de una tarifa indexada.
- Alimenta `procurement.compare_offers` si se añaden permanencias y cuotas.
- Base de `energy.self_consumption_payback` (ahorro con autoconsumo).

## 8. Decisiones pendientes

- Periodos horarios P1/P2/P3 (2.0TD/3.0TD) y potencias por periodo.
- Impuestos (IVA, impuesto eléctrico) y excedentes de autoconsumo.
- Tarifas indexadas con fórmula PVPC + margen.
- Validar el perfil de consumo con datos reales del usuario (curva horaria).
