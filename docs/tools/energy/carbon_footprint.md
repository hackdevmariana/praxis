---
estado: v2
version: 0.1.0
tool: energy.carbon_footprint
---

# `energy.carbon_footprint` — Huella de carbono

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `energy.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (factores versionados) |
| Caché | n/a |
| Perfiles | `praxis-biz`, `praxis-sim` |

## 2. Semántica exacta

Calcula emisiones de GEI (kgCO₂e) por alcance a partir de consumos.

| Fuente | Alcance | Factor por defecto |
|---|---|---|
| Electricidad | 2 | 0.150 kgCO₂e/kWh |
| Gas natural | 1 | 0.202 kgCO₂e/kWh |
| Diésel | 1 | 2.680 kgCO₂e/L |
| Gasolina | 1 | 2.310 kgCO₂e/L |
| Residuos | 3 | 0.500 kgCO₂e/kg |
| Transporte (km) | 3 | 0.120 kgCO₂e/km |

- `scope1 = gas + diésel + gasolina`.
- `scope2 = electricidad`.
- `scope3 = residuos + transporte`.
- `total = scope1 + scope2 + scope3`.
- `intensity_kgco2e_per_kwh = total / (electricity_kwh + gas_kwh)` si el denominador `> 0`; si no, `null`.
- `factor_overrides` permite sustituir cualquier factor (mismas claves); si se usa, warning `custom_factors` y `is_estimated=false` para los factores sustituidos (se documenta en `metadata.factors_source`).
- `period_start`/`period_end` opcionales, ambos o ninguno; si ambos, `start ≤ end`.

Reglas:

- Todos los consumos `≥ 0`; se devuelve el desglose `by_source` con `activity`, `factor`, `emissions`.
- Importes/emisiones con 2 decimales (`ROUND_HALF_UP`); intensidad con 4 decimales.
- **Doble cómputo:** si se aportan litros de combustible y `transport_km`, se emite warning `possible_double_counting` (el usuario debe elegir una vía).
- Factores por defecto son genéricos de España y están versionados (`factors_version`); no sustituyen un inventario corporativo auditado.
- No se incluyen alcance 3 completo (compras, viajes de negocio, cadena de suministro): solo las fuentes indicadas.
- `is_estimated=true` y disclaimer legal.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

class CarbonInput(BaseModel):
    electricity_kwh: Decimal = Field(default=Decimal("0"), ge=0)
    gas_kwh: Decimal = Field(default=Decimal("0"), ge=0)
    diesel_liters: Decimal = Field(default=Decimal("0"), ge=0)
    gasoline_liters: Decimal = Field(default=Decimal("0"), ge=0)
    waste_kg: Decimal = Field(default=Decimal("0"), ge=0)
    transport_km: Decimal = Field(default=Decimal("0"), ge=0)
    period_start: date | None = None
    period_end: date | None = None
    factor_overrides: dict[str, Decimal] | None = None

    @model_validator(mode="after")
    def periodo(self):
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("Aporta period_start y period_end juntos")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("period_start no puede ser posterior a period_end")
        return self

class SourceEmission(BaseModel):
    activity: str
    scope: int
    quantity: Decimal
    unit: str
    factor: Decimal
    emissions_kgco2e: Decimal

class CarbonOutput(BaseModel):
    period_start: date | None
    period_end: date | None
    scope1_kgco2e: Decimal
    scope2_kgco2e: Decimal
    scope3_kgco2e: Decimal
    total_kgco2e: Decimal
    intensity_kgco2e_per_kwh: Decimal | None
    by_source: list[SourceEmission]
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | 10000 kWh luz, 5000 kWh gas, 500 L diésel, 200 L gasolina, 300 kg residuos, 2000 km | total 4702.00, alcances 2812/1500/390 |
| Solo electricidad | 1000 kWh | scope2 150.00 |
| Solo gas | 1000 kWh | scope1 202.00 |
| Factores propios | `factor_overrides={"electricity": 0.10}` | warning `custom_factors`, scope2 1000.00 |
| Doble cómputo | diésel + transporte | warning `possible_double_counting` |
| Sin consumos | todo 0 | total 0.00, intensidad `null` |
| Periodo parcial | solo `period_start` | error `invalid_params` |
| Periodo invertido | start > end | error `invalid_params` |
| Factor negativo | override < 0 | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "electricity_kwh": "10000",
    "gas_kwh": "5000",
    "diesel_liters": "500",
    "gasoline_liters": "200",
    "waste_kg": "300",
    "transport_km": "2000",
    "period_start": "2026-01-01",
    "period_end": "2026-12-31"
  },
  "output": {
    "period_start": "2026-01-01",
    "period_end": "2026-12-31",
    "scope1_kgco2e": "2812.00",
    "scope2_kgco2e": "1500.00",
    "scope3_kgco2e": "390.00",
    "total_kgco2e": "4702.00",
    "intensity_kgco2e_per_kwh": "0.3135",
    "by_source": [
      { "activity": "electricity", "scope": 2, "quantity": "10000", "unit": "kWh", "factor": "0.150", "emissions_kgco2e": "1500.00" },
      { "activity": "natural_gas", "scope": 1, "quantity": "5000", "unit": "kWh", "factor": "0.202", "emissions_kgco2e": "1010.00" },
      { "activity": "diesel", "scope": 1, "quantity": "500", "unit": "L", "factor": "2.680", "emissions_kgco2e": "1340.00" },
      { "activity": "gasoline", "scope": 1, "quantity": "200", "unit": "L", "factor": "2.310", "emissions_kgco2e": "462.00" },
      { "activity": "waste", "scope": 3, "quantity": "300", "unit": "kg", "factor": "0.500", "emissions_kgco2e": "150.00" },
      { "activity": "transport", "scope": 3, "quantity": "2000", "unit": "km", "factor": "0.120", "emissions_kgco2e": "240.00" }
    ]
  },
  "metadata": { "warnings": ["possible_double_counting"] }
}
```

```json
{
  "input": { "electricity_kwh": "1000" },
  "output": {
    "scope1_kgco2e": "0.00",
    "scope2_kgco2e": "150.00",
    "scope3_kgco2e": "0.00",
    "total_kgco2e": "150.00",
    "intensity_kgco2e_per_kwh": "0.1500",
    "by_source": [
      { "activity": "electricity", "scope": 2, "quantity": "1000", "unit": "kWh", "factor": "0.150", "emissions_kgco2e": "150.00" }
    ]
  }
}
```

```json
{
  "input": { "electricity_kwh": "1000", "factor_overrides": { "electricity": "0.10" } },
  "output": {
    "scope2_kgco2e": "100.00",
    "total_kgco2e": "100.00"
  },
  "metadata": { "warnings": ["custom_factors"], "factors_source": "custom" }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "calculation",
  "is_estimated": true,
  "confidence": 0.7,
  "unit": "kgCO2e",
  "factors_version": "2026.1",
  "factors_source": "default",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa consumos de `energy.pvpc_hourly` o facturas extraídas con `documents.extract_invoice`.
- Base de `energy.self_consumption_payback` (emisiones evitadas) y de informes ESG (v3).
- Combinable con `finance.business_kpi` para intensidad por facturación.

## 8. Decisiones pendientes

- Pendiente: factores oficiales por año y comunidad (MITECO) y factores de mercado (location-based vs market-based); dataset.
- Pendiente: alcance 3 ampliado (compras, viajes, cadena de suministro); decisión de producto.
- Pendiente: verificación/auditoría del inventario y exportación a formatos GHG Protocol; requiere auditoría externa.
- Pendiente: evitar doble cómputo automáticamente cuando el combustible se usa para transporte; decisión de producto.
