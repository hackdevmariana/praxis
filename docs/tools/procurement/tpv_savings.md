---
estado: MVP
version: 1.0.0
tool: procurement.tpv_savings
---

# `procurement.tpv_savings` — Ahorro por cambio de TPV

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `procurement.calculate` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista |
| Caché | n/a |
| Perfiles | `praxis-biz` (asociación) |

## 2. Semántica exacta

Compara el coste anual de comisiones de TPV actual frente a una oferta nueva.

- `current_cost = round(annual_card_turnover × current_rate_pct / 100)`
- `new_cost = round(annual_card_turnover × new_rate_pct / 100)`
- `annual_savings = current_cost − new_cost` (negativo si la oferta es más cara)
- `monthly_savings = round(annual_savings / 12)`
- `savings_pct = round(annual_savings / current_cost × 100)` si `current_cost > 0`; si no, `null` + warning `undefined_savings_pct`
- `savings_per_ticket = round(annual_savings / (turnover / average_ticket))` si se aporta `average_ticket`; si no, `null`

Reglas:

- No se incluyen cuotas fijas, alquiler de terminal ni penalizaciones: solo comisión porcentual.
- `annual_card_turnover ≥ 0`; `current_rate_pct` y `new_rate_pct ∈ [0, 100]`.
- `average_ticket > 0` si se aporta.
- Importes en `Decimal`, 2 decimales (`ROUND_HALF_UP`); porcentajes con 2 decimales.
- El resultado es una estimación: `is_estimated=true` y disclaimer legal en `metadata`.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class TpvSavingsInput(BaseModel):
    annual_card_turnover: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    current_rate_pct: Decimal = Field(ge=0, le=100)
    new_rate_pct: Decimal = Field(ge=0, le=100)
    average_ticket: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

class TpvSavingsOutput(BaseModel):
    current_cost: Decimal
    new_cost: Decimal
    annual_savings: Decimal
    monthly_savings: Decimal
    savings_pct: Decimal | None
    savings_per_ticket: Decimal | None
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Ahorro típico | turnover 500000, 1.5% → 0.9%, ticket 25 | ahorro 3000.00, mensual 250.00, 40.00%, 0.15/ticket |
| Tipos iguales | 100000, 1.0% → 1.0% | ahorro 0.00, 0.00% |
| Oferta más cara | 100000, 1.0% → 1.2% | ahorro −200.00, mensual −16.67, −20.00% |
| Sin ticket medio | ticket omitido | `savings_per_ticket=null` |
| Coste actual cero | 100000, 0% → 1% | `savings_pct=null`, warning |
| Turnover cero | 0, 1.5% → 0.9% | todo 0.00, `savings_pct=null` |
| Tipo fuera de rango | 1.5% → 101% | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "annual_card_turnover": "500000",
    "current_rate_pct": "1.5",
    "new_rate_pct": "0.9",
    "average_ticket": "25"
  },
  "output": {
    "current_cost": "7500.00",
    "new_cost": "4500.00",
    "annual_savings": "3000.00",
    "monthly_savings": "250.00",
    "savings_pct": "40.00",
    "savings_per_ticket": "0.15",
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "annual_card_turnover": "100000",
    "current_rate_pct": "1.0",
    "new_rate_pct": "1.2"
  },
  "output": {
    "current_cost": "1000.00",
    "new_cost": "1200.00",
    "annual_savings": "-200.00",
    "monthly_savings": "-16.67",
    "savings_pct": "-20.00",
    "savings_per_ticket": null,
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "annual_card_turnover": "100000",
    "current_rate_pct": "0",
    "new_rate_pct": "1"
  },
  "output": {
    "current_cost": "0.00",
    "new_cost": "1000.00",
    "annual_savings": "-1000.00",
    "monthly_savings": "-83.33",
    "savings_pct": null,
    "savings_per_ticket": null,
    "currency": "EUR"
  },
  "metadata": { "warnings": ["undefined_savings_pct"] }
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
  "confidence": 0.9,
  "currency": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Alimenta `savings_ledger` (v2) con el ahorro anual estimado.
- Combinada con `procurement.compare_offers` para comparar ofertas completas de TPV (comisión + cuotas).
- Base de informes de la asociación (`sim.hiring_simulator` no aplica aquí).

## 8. Decisiones pendientes

- Incluir cuota fija mensual, alquiler de terminal y coste de integración como campos opcionales en v1.1.
- Soportar tramos de comisión (debit/credit, nacional/internacional) además del tipo único.
- Verificar límites legales de comisiones (interchange) antes de afirmar ahorros.
