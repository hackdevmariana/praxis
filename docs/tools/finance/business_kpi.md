---
estado: v2
version: 0.1.0
tool: finance.business_kpi
---

# `finance.business_kpi` — KPIs financieros básicos

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

Calcula márgenes, rentabilidad y ciclo de caja a partir de un estado financiero resumido.

| KPI | Fórmula |
|---|---|
| `gross_profit` | `revenue − cogs` |
| `gross_margin_pct` | `gross_profit / revenue × 100` |
| `ebit` | `gross_profit − operating_expenses` |
| `ebit_margin_pct` | `ebit / revenue × 100` |
| `ebitda` | `ebit + depreciation_amortization` |
| `dso_days` | `receivables / revenue × period_days` |
| `dpo_days` | `payables / cogs × period_days` |
| `dio_days` | `inventory / cogs × period_days` |
| `cash_conversion_cycle_days` | `dso + dio − dpo` |
| `current_ratio` | `(cash + receivables + inventory) / current_liabilities` |
| `working_capital` | `(cash + receivables + inventory) − current_liabilities` |

Reglas:

- Todos los importes `≥ 0` (las pérdidas se reflejan en `ebit` negativo calculado).
- Si un denominador es `0` → el KPI es `null` + warning `undefined_ratio` (nunca `Infinity`/`NaN`).
- `period_days ∈ [30, 366]`, por defecto `365`.
- Importes con 2 decimales; ratios con 2; días con 2.
- `is_estimated=true`: los datos son aportados y no sustituyen a un estado contable auditado.
- No incluye impuestos ni intereses; para resultado neto se necesita información adicional.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class BusinessKpiInput(BaseModel):
    revenue: Decimal = Field(ge=0)
    cogs: Decimal = Field(ge=0)
    operating_expenses: Decimal = Field(ge=0)
    depreciation_amortization: Decimal = Field(default=Decimal("0"), ge=0)
    receivables: Decimal = Field(default=Decimal("0"), ge=0)
    payables: Decimal = Field(default=Decimal("0"), ge=0)
    inventory: Decimal = Field(default=Decimal("0"), ge=0)
    cash: Decimal = Field(default=Decimal("0"), ge=0)
    current_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    period_days: int = Field(default=365, ge=30, le=366)
    currency: str = "EUR"

class BusinessKpiOutput(BaseModel):
    gross_profit: Decimal
    gross_margin_pct: Decimal | None
    ebit: Decimal
    ebit_margin_pct: Decimal | None
    ebitda: Decimal
    dso_days: Decimal | None
    dpo_days: Decimal | None
    dio_days: Decimal | None
    cash_conversion_cycle_days: Decimal | None
    current_ratio: Decimal | None
    working_capital: Decimal
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | 1.000.000 ingresos, 600.000 COGS, 250.000 opex, 50.000 D&A | margen bruto 40%, EBIT 15%, EBITDA 200.000 |
| Ciclo de caja | 120k cobros, 80k pagos, 90k inventario | DSO 43.80, DPO 48.67, DIO 54.75, CCC 49.88 |
| Liquidez | 60k caja, 150k pasivo corriente | current ratio 1.80, working capital 120.000 |
| Sin ingresos | `revenue=0` | márgenes `null`, warning |
| Sin COGS | `cogs=0` | DPO/DIO `null` |
| Pérdida | opex > margen bruto | EBIT negativo |
| Periodo trimestral | `period_days=90` | DSO/DPO/DIO escalados |

## 5. Golden cases

```json
{
  "input": {
    "revenue": "1000000",
    "cogs": "600000",
    "operating_expenses": "250000",
    "depreciation_amortization": "50000",
    "receivables": "120000",
    "payables": "80000",
    "inventory": "90000",
    "cash": "60000",
    "current_liabilities": "150000",
    "period_days": 365
  },
  "output": {
    "gross_profit": "400000.00",
    "gross_margin_pct": "40.00",
    "ebit": "150000.00",
    "ebit_margin_pct": "15.00",
    "ebitda": "200000.00",
    "dso_days": "43.80",
    "dpo_days": "48.67",
    "dio_days": "54.75",
    "cash_conversion_cycle_days": "49.88",
    "current_ratio": "1.80",
    "working_capital": "120000.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "revenue": "0", "cogs": "0", "operating_expenses": "1000", "current_liabilities": "0" },
  "output": {
    "gross_profit": "0.00",
    "gross_margin_pct": null,
    "ebit": "-1000.00",
    "ebit_margin_pct": null,
    "ebitda": "-1000.00",
    "dso_days": null,
    "dpo_days": null,
    "dio_days": null,
    "cash_conversion_cycle_days": null,
    "current_ratio": null,
    "working_capital": "0.00",
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

- Consume datos de `documents.extract_invoice` y de la contabilidad del tenant (v2).
- Alimenta `finance.ebitda`, `finance.break_even` y `finance.cashflow_13w`.
- Base de informes comparativos y semáforos (`KPIThreshold`) del tenant.

## 8. Decisiones pendientes

- KPIs por sector y comparativas (benchmark) con `praxis-knowledge`.
- DSO/DPO ponderados por importe y por vencimiento, no solo saldo medio.
- Inclusión de impuestos/intereses para resultado neto y ROE/ROA.
- Validar fórmulas con gestoría antes de publicar como referencia.
