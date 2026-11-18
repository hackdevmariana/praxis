---
estado: v2
version: 0.1.0
tool: finance.ebitda
---

# `finance.ebitda` — EBITDA y EBITDA ajustado

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

Calcula EBITDA, EBITDA ajustado y EBIT.

- `ebitda = revenue − cogs − operating_expenses`.
- `adjusted_ebitda = ebitda − non_recurring_income + non_recurring_expenses` (se eliminan partidas no recurrentes).
- `ebit = ebitda − depreciation_amortization`.
- `ebitda_margin_pct = ebitda / revenue × 100`.
- `adjusted_ebitda_margin_pct = adjusted_ebitda / revenue × 100`.
- `ebit_margin_pct = ebit / revenue × 100`.

Reglas:

- `revenue`, `cogs`, `operating_expenses`, `depreciation_amortization`, partidas no recurrentes: `≥ 0`.
- Si `revenue = 0` → márgenes `null` + warning `undefined_ratio`.
- `operating_expenses` **excluye** amortizaciones (se aportan aparte).
- Partidas no recurrentes: ingresos extraordinarios se restan y gastos extraordinarios se suman para aproximar la capacidad recurrente.
- Importes 2 decimales; porcentajes 2.
- No se calcula beneficio neto (faltan intereses e impuestos).
- `is_estimated=true` y disclaimer: no es una cifra auditada.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class EbitdaInput(BaseModel):
    revenue: Decimal = Field(ge=0)
    cogs: Decimal = Field(ge=0)
    operating_expenses: Decimal = Field(ge=0)
    depreciation_amortization: Decimal = Field(default=Decimal("0"), ge=0)
    non_recurring_income: Decimal = Field(default=Decimal("0"), ge=0)
    non_recurring_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = "EUR"

class EbitdaOutput(BaseModel):
    ebitda: Decimal
    adjusted_ebitda: Decimal
    ebit: Decimal
    ebitda_margin_pct: Decimal | None
    adjusted_ebitda_margin_pct: Decimal | None
    ebit_margin_pct: Decimal | None
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | 1M ingresos, 600k COGS, 250k opex, 50k D&A | EBITDA 150.000, EBIT 100.000, margen 15% |
| Partidas no recurrentes | +20k ingreso, +10k gasto | ajustado 140.000 (14%) |
| Sin D&A | D&A 0 | EBIT = EBITDA |
| Sin ingresos | `revenue=0` | márgenes `null`, warning |
| Pérdida operativa | opex alto | EBITDA negativo |
| Importe negativo | `cogs=-1` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "revenue": "1000000",
    "cogs": "600000",
    "operating_expenses": "250000",
    "depreciation_amortization": "50000",
    "non_recurring_income": "20000",
    "non_recurring_expenses": "10000"
  },
  "output": {
    "ebitda": "150000.00",
    "adjusted_ebitda": "140000.00",
    "ebit": "100000.00",
    "ebitda_margin_pct": "15.00",
    "adjusted_ebitda_margin_pct": "14.00",
    "ebit_margin_pct": "10.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "revenue": "0", "cogs": "0", "operating_expenses": "5000" },
  "output": {
    "ebitda": "-5000.00",
    "adjusted_ebitda": "-5000.00",
    "ebit": "-5000.00",
    "ebitda_margin_pct": null,
    "adjusted_ebitda_margin_pct": null,
    "ebit_margin_pct": null,
    "currency": "EUR"
  },
  "metadata": { "warnings": ["undefined_ratio"] }
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
  "confidence": 0.8,
  "currency": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa la base de `finance.business_kpi`.
- Alimenta `finance.break_even` y valoraciones (múltiplos EBITDA) en v3.
- Combinable con `finance.loan_schedule` para cobertura de deuda (EBITDA/deuda).

## 8. Decisiones pendientes

- Pendiente: ajustes normalizados por sector y por tamaño; decisión de producto.
- Pendiente: EBITDA por segmento de negocio; decisión de producto.
- Pendiente: tratamiento de arrendamientos (IFRS 16) y comparabilidad con PYMES; validación profesional.
- Pendiente: validación con gestoría de las partidas no recurrentes; validación profesional.
