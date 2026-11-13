---
estado: v2
version: 0.1.0
tool: procurement.savings_ledger
---

# `procurement.savings_ledger` — Registro de ahorros

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `procurement.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | base de datos del tenant (RLS) |
| Caché | n/a |
| Perfiles | `praxis-biz` (asociación) |

## 2. Semántica exacta

Agrega el registro de ahorros del tenant (alimentado por `procurement.tpv_savings`, `procurement.compare_offers`, `procurement.detect_price_increase` y altas manuales).

- `savings = baseline_cost − actual_cost` (puede ser negativo si el resultado empeoró).
- `annualized_savings` se toma del registro (ya anualizado por la tool de origen).
- Filtros: rango `[period_start, period_end]` por fecha del registro, `category` opcional y `status` opcional.
- `total_savings = Σ savings`; `total_annualized = Σ annualized_savings`.
- `by_category`: suma de `savings` y `annualized_savings` por categoría.
- Orden de `entries`: fecha descendente, luego importe descendente.
- Si el periodo no tiene registros → listas vacías y `total_savings=0.00` (no es error).

Reglas:

- `period_start ≤ period_end`; si se omite el periodo, se usa el año natural en curso (según reloj del servidor).
- `category ∈ {tpv, supplies, energy, other}`.
- `status ∈ {realized, projected, all}`; `all` por defecto.
- Importes 2 decimales.
- Solo lectura: las altas se hacen desde las tools de origen o la interfaz; aquí no se escribe.
- RLS por `company_id`: nunca se mezclan registros entre tenants.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class SavingsCategory(str, Enum):
    tpv = "tpv"
    supplies = "supplies"
    energy = "energy"
    other = "other"

class SavingsStatus(str, Enum):
    realized = "realized"
    projected = "projected"
    all = "all"

class SavingsLedgerInput(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    category: SavingsCategory | None = None
    status: SavingsStatus = SavingsStatus.all
    currency: str = "EUR"

    @model_validator(mode="after")
    def periodo(self):
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("Aporta period_start y period_end juntos")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("period_start no puede ser posterior a period_end")
        return self

class SavingsEntry(BaseModel):
    id: str
    date: date
    category: SavingsCategory
    supplier: str | None
    description: str
    baseline_cost: Decimal
    actual_cost: Decimal
    savings: Decimal
    annualized_savings: Decimal
    status: str

class CategoryTotal(BaseModel):
    category: SavingsCategory
    savings: Decimal
    annualized_savings: Decimal
    count: int

class SavingsLedgerOutput(BaseModel):
    period_start: date
    period_end: date
    entries: list[SavingsEntry]
    total_savings: Decimal
    total_annualized: Decimal
    by_category: list[CategoryTotal]
    count: int
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Tres registros | TPV 3.000, energía 1.200, suministros 800 | total 5.000, anualizado 5.200 |
| Filtro por categoría | `category=energy` | solo el registro de energía |
| Solo realizados | `status=realized` | excluye proyectados |
| Periodo vacío | rango sin registros | totales 0, `count=0` |
| Ahorro negativo | actual > baseline | `savings` negativo, reduce el total |
| Rango invertido | start > end | error `invalid_params` |
| Periodo parcial | solo `period_start` | error `invalid_params` |

## 5. Golden cases

Fixture `savings-ledger-2026.json` (tres registros del tenant).

```json
{
  "input": { "period_start": "2026-01-01", "period_end": "2026-12-31", "status": "all" },
  "output": {
    "period_start": "2026-01-01",
    "period_end": "2026-12-31",
    "count": 3,
    "total_savings": "5000.00",
    "total_annualized": "5200.00",
    "currency": "EUR",
    "by_category": [
      { "category": "tpv", "savings": "3000.00", "annualized_savings": "3000.00", "count": 1 },
      { "category": "energy", "savings": "1200.00", "annualized_savings": "1400.00", "count": 1 },
      { "category": "supplies", "savings": "800.00", "annualized_savings": "800.00", "count": 1 }
    ],
    "entries": [
      { "id": "sv_003", "date": "2026-11-10", "category": "supplies", "supplier": "Molinos S.A.", "description": "Renegociación de harina", "baseline_cost": "12000.00", "actual_cost": "11200.00", "savings": "800.00", "annualized_savings": "800.00", "status": "projected" },
      { "id": "sv_002", "date": "2026-06-01", "category": "energy", "supplier": "Eléctrica X", "description": "Cambio de tarifa", "baseline_cost": "4200.00", "actual_cost": "3000.00", "savings": "1200.00", "annualized_savings": "1400.00", "status": "realized" },
      { "id": "sv_001", "date": "2026-02-15", "category": "tpv", "supplier": "TPV Y", "description": "Cambio de comisión TPV", "baseline_cost": "7500.00", "actual_cost": "4500.00", "savings": "3000.00", "annualized_savings": "3000.00", "status": "realized" }
    ]
  }
}
```

```json
{
  "input": { "period_start": "2026-01-01", "period_end": "2026-12-31", "category": "energy" },
  "output": {
    "count": 1,
    "total_savings": "1200.00",
    "total_annualized": "1400.00"
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "database",
  "source_type": "database",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "aggregation",
  "is_estimated": false,
  "currency": "EUR",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Alimentado por `procurement.tpv_savings`, `procurement.compare_offers` y `procurement.detect_price_increase`.
- Base de informes de la asociación y de `finance.business_kpi` (ahorro como palanca de margen).
- En v2, exportación a CSV/Excel.

## 8. Decisiones pendientes

- Modelo de alta manual y aprobación de ahorros proyectados.
- Amortización temporal del ahorro (mensual vs anualizado).
- Evitar doble conteo entre herramientas que miden el mismo ahorro.
- Moneda: ¿consolidar en EUR con `currency.convert` o exigir misma divisa?
