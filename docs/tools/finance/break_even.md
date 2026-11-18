---
estado: v2
version: 0.1.0
tool: finance.break_even
---

# `finance.break_even` — Punto de equilibrio

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `finance.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista |
| Caché | n/a |
| Perfiles | `praxis-biz` |

## 2. Semántica exacta

Calcula el punto de equilibrio y el margen de seguridad.

- `contribution_margin_per_unit = price_per_unit − variable_cost_per_unit`.
- `contribution_margin_pct = contribution_margin_per_unit / price_per_unit × 100`.
- `break_even_units = ceil(fixed_costs / contribution_margin_per_unit)` (unidades enteras).
- `break_even_revenue = round(fixed_costs / (contribution_margin_pct/100))` (ingresos exactos; puede no coincidir con `break_even_units × price` por el redondeo al alza de unidades).
- `units_for_target_profit = ceil((fixed_costs + target_profit) / contribution_margin_per_unit)`.
- Si se aporta `expected_units`:
  - `margin_of_safety_units = expected_units − break_even_units`.
  - `margin_of_safety_pct = margin_of_safety_units / expected_units × 100`.

Reglas:

- `fixed_costs ≥ 0`, `variable_cost_per_unit ≥ 0`, `price_per_unit > 0`, `target_profit ≥ 0`, `expected_units ≥ 0`.
- Si `contribution_margin_per_unit ≤ 0` → error `invalid_params` (con ese precio no hay equilibrio).
- Importes 2 decimales; porcentajes 2; unidades enteras.
- No se incluyen impuestos ni costes financieros.
- `is_estimated=true`; los costes fijos/variables son aportados.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class BreakEvenInput(BaseModel):
    fixed_costs: Decimal = Field(ge=0)
    variable_cost_per_unit: Decimal = Field(ge=0)
    price_per_unit: Decimal = Field(gt=0)
    target_profit: Decimal = Field(default=Decimal("0"), ge=0)
    expected_units: int | None = Field(default=None, ge=0)
    currency: str = "EUR"

class BreakEvenOutput(BaseModel):
    contribution_margin_per_unit: Decimal
    contribution_margin_pct: Decimal
    break_even_units: int
    break_even_revenue: Decimal
    units_for_target_profit: int
    margin_of_safety_units: int | None
    margin_of_safety_pct: Decimal | None
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | fijos 100.000, variable 20, precio 50 | CM 30 (60%), 3.334 uds, ingresos 166.666,67 |
| Con objetivo | `target_profit=30000` | 4.334 uds |
| Margen de seguridad | `expected_units=5000` | 1.666 uds, 33,32% |
| Sin objetivo | `target_profit=0` | igual al break-even |
| Precio = coste variable | precio 20, variable 20 | error `invalid_params` |
| Precio menor | precio 15 | error `invalid_params` |
| Precio cero | `price_per_unit=0` | error `invalid_params` |
| Unidades esperadas 0 | `expected_units=0` | MoS `null` |

## 5. Golden cases

```json
{
  "input": {
    "fixed_costs": "100000",
    "variable_cost_per_unit": "20",
    "price_per_unit": "50",
    "target_profit": "30000",
    "expected_units": 5000
  },
  "output": {
    "contribution_margin_per_unit": "30.00",
    "contribution_margin_pct": "60.00",
    "break_even_units": 3334,
    "break_even_revenue": "166666.67",
    "units_for_target_profit": 4334,
    "margin_of_safety_units": 1666,
    "margin_of_safety_pct": "33.32",
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "fixed_costs": "100000",
    "variable_cost_per_unit": "20",
    "price_per_unit": "50",
    "target_profit": "0"
  },
  "output": {
    "contribution_margin_per_unit": "30.00",
    "contribution_margin_pct": "60.00",
    "break_even_units": 3334,
    "break_even_revenue": "166666.67",
    "units_for_target_profit": 3334,
    "margin_of_safety_units": null,
    "margin_of_safety_pct": null,
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "fixed_costs": "10000",
    "variable_cost_per_unit": "20",
    "price_per_unit": "20"
  },
  "output": null,
  "error": { "code": "invalid_params", "message": "El margen de contribución debe ser positivo" }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "user_input",
  "source_type": "user_input",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "calculation",
  "is_estimated": true,
  "confidence": 0.85,
  "currency": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa `finance.business_kpi` y `finance.ebitda` para fijar costes.
- Alimenta `sim.hiring_simulator` (punto de equilibrio con un comercial más).
- Combinable con `finance.cashflow_13w` para ver si el equilibrio llega en plazo.

## 8. Decisiones pendientes

- Pendiente: punto de equilibrio multiproducto (mix de ventas y márgenes por producto); decisión de producto.
- Pendiente: costes fijos escalonados (tramos) y economías de escala; decisión de producto.
- Pendiente: impuestos y coste financiero en una variante "break-even neto"; validación legal.
