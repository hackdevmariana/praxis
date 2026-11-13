---
estado: v2
version: 0.1.0
tool: finance.cashflow_13w
---

# `finance.cashflow_13w` — Previsión de tesorería a 13 semanas

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

Proyecta la tesorería semana a semana durante 13 semanas.

- `net_i = inflow_i − outflow_i`.
- `closing_balance_i = closing_balance_{i−1} + net_i`, con `closing_balance_0 = opening_balance`.
- `week_start_i = start_date + 7 × (i − 1)` si se aporta `start_date`; si no, `null`.
- `min_balance` y `min_week` sobre los cierres semanales.
- `weeks_with_negative_balance` = número de semanas con cierre `< 0`.
- `end_balance` = cierre de la semana 13.
- Si algún cierre es negativo → warning `negative_balance_risk`.

Reglas:

- `weekly_inflows` y `weekly_outflows` deben tener **exactamente 13** elementos cada una.
- Importes `≥ 0`; `opening_balance` puede ser negativo.
- Importes con 2 decimales (`ROUND_HALF_UP`).
- No se modelan impuestos, financiación nueva ni estacionalidad: es una previsión lineal con los datos aportados.
- `is_estimated=true` y disclaimer.

## 3. Contrato Pydantic

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

class Cashflow13wInput(BaseModel):
    opening_balance: Decimal
    weekly_inflows: list[Decimal] = Field(min_length=13, max_length=13)
    weekly_outflows: list[Decimal] = Field(min_length=13, max_length=13)
    start_date: date | None = None
    currency: str = "EUR"

    @field_validator("weekly_inflows", "weekly_outflows")
    @classmethod
    def no_negativos(cls, v):
        if any(x < 0 for x in v):
            raise ValueError("Los importes semanales no pueden ser negativos")
        return v

class CashflowWeek(BaseModel):
    week: int
    week_start: date | None
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    closing_balance: Decimal

class Cashflow13wOutput(BaseModel):
    opening_balance: Decimal
    weeks: list[CashflowWeek]
    end_balance: Decimal
    min_balance: Decimal
    min_week: int
    weeks_with_negative_balance: int
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | apertura 10.000, entrada 5.000, salida 6.000 | cierre −3.000, mínimo semana 13 |
| Flujo positivo | entrada 7.000, salida 5.000 | cierre 36.000, sin warnings |
| Apertura negativa | apertura −5.000 | todas las semanas negativas |
| Cero exacto | cierre semanal 0 | no cuenta como negativo |
| Lista de 12 | `weekly_inflows` con 12 | error `invalid_params` |
| Importe negativo | salida −100 | error `invalid_params` |
| Con fechas | `start_date=2026-11-16` | `week_start` semanal |

## 5. Golden cases

```json
{
  "input": {
    "opening_balance": "10000",
    "weekly_inflows": ["5000","5000","5000","5000","5000","5000","5000","5000","5000","5000","5000","5000","5000"],
    "weekly_outflows": ["6000","6000","6000","6000","6000","6000","6000","6000","6000","6000","6000","6000","6000"],
    "start_date": "2026-11-16"
  },
  "output": {
    "opening_balance": "10000.00",
    "end_balance": "-3000.00",
    "min_balance": "-3000.00",
    "min_week": 13,
    "weeks_with_negative_balance": 3,
    "weeks": [
      { "week": 1, "week_start": "2026-11-16", "inflow": "5000.00", "outflow": "6000.00", "net": "-1000.00", "closing_balance": "9000.00" },
      { "week": 2, "week_start": "2026-11-23", "inflow": "5000.00", "outflow": "6000.00", "net": "-1000.00", "closing_balance": "8000.00" },
      { "week": 10, "week_start": "2027-01-18", "inflow": "5000.00", "outflow": "6000.00", "net": "-1000.00", "closing_balance": "0.00" },
      { "week": 11, "week_start": "2027-01-25", "inflow": "5000.00", "outflow": "6000.00", "net": "-1000.00", "closing_balance": "-1000.00" },
      { "week": 12, "week_start": "2027-02-01", "inflow": "5000.00", "outflow": "6000.00", "net": "-1000.00", "closing_balance": "-2000.00" },
      { "week": 13, "week_start": "2027-02-08", "inflow": "5000.00", "outflow": "6000.00", "net": "-1000.00", "closing_balance": "-3000.00" }
    ],
    "currency": "EUR"
  },
  "note": "El golden completo tiene 13 semanas; aquí se muestran las 3 primeras y las 4 últimas",
  "metadata": { "warnings": ["negative_balance_risk"] }
}
```

```json
{
  "input": {
    "opening_balance": "0",
    "weekly_inflows": ["7000","7000","7000","7000","7000","7000","7000","7000","7000","7000","7000","7000","7000"],
    "weekly_outflows": ["5000","5000","5000","5000","5000","5000","5000","5000","5000","5000","5000","5000","5000"]
  },
  "output": {
    "end_balance": "26000.00",
    "min_balance": "2000.00",
    "min_week": 1,
    "weeks_with_negative_balance": 0
  }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "user_input",
  "source_type": "user_input",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "forecast",
  "is_estimated": true,
  "confidence": 0.7,
  "currency": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa `finance.loan_schedule` para incluir cuotas de préstamo en las salidas.
- Puede consumir `documents.extract_invoice` para programar cobros y pagos.
- Base de `alerts.*` para avisar de tensión de liquidez.

## 8. Decisiones pendientes

- Escenarios (optimista/base/pesimista) y comparación.
- Fechas de cobro/pago por factura (vencimientos reales) en lugar de agregados semanales.
- Impuestos, nóminas y financiación (confirming/factoring).
- Exportación a Excel/CSV y gráficos.
