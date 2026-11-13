---
estado: v2
version: 0.1.0
tool: sim.hiring_simulator
---

# `sim.hiring_simulator` — Simulador de contratación

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `sim.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (modelo de costes) |
| Caché | n/a |
| Perfiles | `praxis-sim` |

## 2. Semántica exacta

Estima el coste y el retorno de contratar `headcount` personas con un salario bruto anual.

Costes:

- `employer_cost_per_employee = gross_annual_salary × (1 + employer_contribution_rate)`.
- `total_annual_employer_cost = employer_cost_per_employee × headcount`.
- `monthly_total_cost = total_annual_employer_cost / 12`.
- `one_off_costs = (recruitment_cost_per_hire + training_cost_per_hire) × headcount`.
- `first_year_total_cost = total_annual_employer_cost + one_off_costs`.

Retorno (si se aporta `expected_annual_revenue_per_employee` y `gross_margin_pct`):

- `first_year_revenue_per_employee = expected × (12 − ramp_up_months) / 12`.
- `annual_gross_profit_total = revenue_total × gross_margin_pct`.
- `net_annual_impact = annual_gross_profit_total − total_annual_employer_cost`.
- `payback_months = one_off_costs / (net_annual_impact / 12)` (solo si `net_annual_impact > 0`).

Reglas:

- `headcount ∈ [1, 100]`; `gross_annual_salary > 0`.
- `employer_contribution_rate_pct ∈ [0, 60]`, por defecto `31`.
- `ramp_up_months ∈ [0, 12]`; reduce los ingresos del primer año, no los costes.
- Si se aporta retorno, deben venir ambos campos (`revenue` y `margin`); si no, los campos de retorno son `null`.
- `gross_margin_pct ∈ [0, 100]`.
- Importes 2 decimales.
- `is_estimated=true`: los costes reales dependen de convenio, bonificaciones y cotizaciones.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

class HiringSimulatorInput(BaseModel):
    role_title: str = Field(min_length=1, max_length=120)
    headcount: int = Field(ge=1, le=100)
    gross_annual_salary: Decimal = Field(gt=0, decimal_places=2)
    employer_contribution_rate_pct: Decimal = Field(ge=0, le=60, default=31)
    recruitment_cost_per_hire: Decimal = Field(ge=0, default=0, decimal_places=2)
    training_cost_per_hire: Decimal = Field(ge=0, default=0, decimal_places=2)
    expected_annual_revenue_per_employee: Decimal | None = Field(default=None, ge=0)
    gross_margin_pct: Decimal | None = Field(default=None, ge=0, le=100)
    ramp_up_months: int = Field(default=0, ge=0, le=12)
    currency: str = "EUR"

    @model_validator(mode="after")
    def retorno(self):
        if (self.expected_annual_revenue_per_employee is None) != (self.gross_margin_pct is None):
            raise ValueError("Aporta revenue y margin juntos")
        return self

class HiringSimulatorOutput(BaseModel):
    employer_cost_per_employee: Decimal
    total_annual_employer_cost: Decimal
    monthly_cost_per_employee: Decimal
    monthly_total_cost: Decimal
    one_off_costs: Decimal
    first_year_total_cost: Decimal
    annual_revenue_total: Decimal | None
    annual_gross_profit_total: Decimal | None
    net_annual_impact: Decimal | None
    payback_months: Decimal | None
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Dos camareros | 2 × 22.000 €, 31%, altas 1.100 € | coste anual 57.640 € |
| Con retorno | 60.000 €/persona, margen 60% | impacto neto +14.360 €, payback 3,68 meses |
| Sin retorno | sin `revenue` | campos de retorno `null` |
| Ramp-up | 3 meses | ingresos del primer año al 75% |
| Una sola persona | `headcount=1` | costes por empleado |
| Retorno incompleto | solo `revenue` | error `invalid_params` |
| Margen inválido | `gross_margin_pct=120` | error `invalid_params` |
| Sin rentabilidad | coste > beneficio | `net_annual_impact` negativo, payback `null` |

## 5. Golden cases

```json
{
  "input": {
    "role_title": "Camarero/a",
    "headcount": 2,
    "gross_annual_salary": "22000",
    "employer_contribution_rate_pct": "31",
    "recruitment_cost_per_hire": "800",
    "training_cost_per_hire": "300",
    "expected_annual_revenue_per_employee": "60000",
    "gross_margin_pct": "60",
    "ramp_up_months": 0
  },
  "output": {
    "employer_cost_per_employee": "28820.00",
    "total_annual_employer_cost": "57640.00",
    "monthly_cost_per_employee": "2401.67",
    "monthly_total_cost": "4803.33",
    "one_off_costs": "2200.00",
    "first_year_total_cost": "59840.00",
    "annual_revenue_total": "120000.00",
    "annual_gross_profit_total": "72000.00",
    "net_annual_impact": "14360.00",
    "payback_months": "3.68",
    "currency": "EUR"
  }
}
```

```json
{
  "input": {
    "role_title": "Camarero/a",
    "headcount": 2,
    "gross_annual_salary": "22000",
    "employer_contribution_rate_pct": "31"
  },
  "output": {
    "employer_cost_per_employee": "28820.00",
    "total_annual_employer_cost": "57640.00",
    "monthly_cost_per_employee": "2401.67",
    "monthly_total_cost": "4803.33",
    "one_off_costs": "0.00",
    "first_year_total_cost": "57640.00",
    "annual_revenue_total": null,
    "annual_gross_profit_total": null,
    "net_annual_impact": null,
    "payback_months": null,
    "currency": "EUR"
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

- Usa `legal.collective_agreement` para salario de convenio.
- Incorpora `legal.severance_calc` en escenarios de rotación.
- Alimenta `finance.cashflow_13w` y `finance.break_even`.

## 8. Decisiones pendientes

- Bonificaciones de cotización y contratos formativos.
- Coste por hora efectiva y absentismo.
- Productividad por rol y curva de rampa no lineal.
- Comparación de escenarios (headcount × salario) en una sola llamada.
