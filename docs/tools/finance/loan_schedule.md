---
estado: MVP
version: 1.0.0
tool: finance.loan_schedule
---

# `finance.loan_schedule` — Generar cuadro de amortización

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `finance.calculate` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista |
| Caché | n/a |
| Perfiles | all |

## 2. Semántica exacta

Genera el cuadro de amortización de un préstamo con tipo fijo.

Parámetros: `principal > 0`, `annual_rate ≥ 0` (tanto por ciento nominal anual), `term_months > 0`, `type ∈ {french, italian}`.

Tipo de interés mensual: `i = annual_rate / 100 / 12`.

| `type` | Cuota | Amortización |
|---|---|---|
| `french` | Constante: `cuota = P·i / (1 − (1+i)^−n)` (si `i=0`, `P/n`) | `amortización = cuota − interés`, creciente |
| `italian` | Variable: `amortización = P/n` constante | `cuota = amortización + interés`, decreciente |

Cálculo por periodo:

1. `interés = round(saldo × i)`
2. `amortización` según el tipo (redondeada a 2 decimales).
3. `cuota = amortización + interés`.
4. `saldo = round(saldo − amortización)`.
5. En el **último periodo** se ajusta la amortización al saldo pendiente para cerrar exactamente en `0.00`.

Reglas:

- Todos los importes en `Decimal`, 2 decimales, `ROUND_HALF_UP`.
- El total pagado es `principal + total_interest`; el último recibo puede diferir unos céntimos por redondeo.
- `annual_rate=0` produce cuotas sin interés.
- El cuadro tiene exactamente `term_months` filas.
- `monthly_payment` es la cuota constante en `french`; en `italian` es `null` (se aportan `first_payment` y `last_payment`).

## 3. Contrato Pydantic

```python
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field

class LoanType(StrEnum):
    french = "french"
    italian = "italian"

class LoanInput(BaseModel):
    principal: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    annual_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    term_months: int = Field(gt=0, le=600)
    type: LoanType = LoanType.french
    currency: str = Field(default="EUR", min_length=3, max_length=3)

class Installment(BaseModel):
    period: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal

class LoanOutput(BaseModel):
    principal: Decimal
    annual_rate: Decimal
    term_months: int
    type: LoanType
    monthly_payment: Decimal | None
    first_payment: Decimal
    last_payment: Decimal
    total_interest: Decimal
    total_paid: Decimal
    schedule: list[Installment]
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Francés 6% 12m | `principal=10000`, `annual_rate=6`, `term_months=12` | cuota 860.66, interés total 327.96 |
| Francés sin interés | `principal=15000`, `annual_rate=0`, `term_months=12` | cuota 1250.00, interés 0.00 |
| Francés corto | `principal=1000`, `annual_rate=12`, `term_months=3` | cuota 340.02, interés 20.07 |
| Italiano 6% 12m | `principal=10000`, `annual_rate=6`, `term_months=12` | 1ª 883.33, última 837.54, interés 325.00 |
| Italiano sin interés | `principal=15000`, `annual_rate=0`, `term_months=12` | 1er/último pago 1250.00, `monthly_payment=null`, interés 0.00 |
| Principal cero | `principal=0` | error `invalid_params` |
| Plazo cero | `term_months=0` | error `invalid_params` |
| Tipo negativo | `annual_rate=-1` | error `invalid_params` |

## 5. Golden cases

Francés 10.000 € al 6% a 12 meses:

```json
{
  "input": { "principal": "10000", "annual_rate": "6", "term_months": 12, "type": "french" },
  "output": {
    "principal": "10000.00",
    "annual_rate": "6",
    "term_months": 12,
    "type": "french",
    "monthly_payment": "860.66",
    "first_payment": "860.66",
    "last_payment": "860.70",
    "total_interest": "327.96",
    "total_paid": "10327.96",
    "schedule": [
      { "period": 1, "payment": "860.66", "interest": "50.00", "principal": "810.66", "balance": "9189.34" },
      { "period": 12, "payment": "860.70", "interest": "4.28", "principal": "856.42", "balance": "0.00" }
    ],
    "currency": "EUR"
  },
  "note": "El array schedule del golden completo tiene 12 filas; aquí se muestran la primera y la última"
}
```

Italiano 10.000 € al 6% a 12 meses:

```json
{
  "input": { "principal": "10000", "annual_rate": "6", "term_months": 12, "type": "italian" },
  "output": {
    "principal": "10000.00",
    "annual_rate": "6",
    "term_months": 12,
    "type": "italian",
    "monthly_payment": null,
    "first_payment": "883.33",
    "last_payment": "837.54",
    "total_interest": "325.00",
    "total_paid": "10325.00",
    "schedule": [
      { "period": 1, "payment": "883.33", "interest": "50.00", "principal": "833.33", "balance": "9166.67" },
      { "period": 12, "payment": "837.54", "interest": "4.17", "principal": "833.37", "balance": "0.00" }
    ],
    "currency": "EUR"
  },
  "note": "El array schedule del golden completo tiene 12 filas; aquí se muestran la primera y la última"
}
```

Francés sin interés:

```json
{
  "input": { "principal": "15000", "annual_rate": "0", "term_months": 12, "type": "french" },
  "output": {
    "monthly_payment": "1250.00",
    "first_payment": "1250.00",
    "last_payment": "1250.00",
    "total_interest": "0.00",
    "total_paid": "15000.00"
  }
}
```

Los campos omitidos en un golden toman el valor por defecto del contrato (`null`).

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "calculation",
  "is_estimated": false,
  "confidence": null,
  "unit_system": "metric",
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": false
}
```

## 7. Composiciones

- Base de `sim.hiring_simulator` (v2) y de simulaciones de inversión (`sim.solar_payback`).
- Usada por `finance.cashflow_13w` (v2) para incluir cuotas de préstamo.
- Relacionada con `finance.break_even` (v2) para costes financieros.

## 8. Decisiones pendientes

- Decidido: parámetros `grace_months` y `rate_schedule` en v2.
- Decidido: `type=american` (solo intereses + devolución final) en v2.
- Implementado: `(1+i)^−n` se calcula con `Decimal` y precisión 60; el redondeo se aplica por periodo al céntimo.
