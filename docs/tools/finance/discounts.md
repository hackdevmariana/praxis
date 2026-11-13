---
estado: MVP
version: 1.0.0
tool: finance.discounts
---

# `finance.discounts` — Descuentos sucesivos

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

Aplica o invierte descuentos porcentuales **sucesivos** (no se suman).

- Factor de descuento: `f = Π(1 − dᵢ/100)`.
- `apply`: `amount` es el precio original → `final = round(amount × f)`.
- `reverse`: `amount` es el precio final → `original = round(amount / f)`.
- Descuento efectivo total: `total_discount_pct = (1 − final/original) × 100`.

Reglas:

- Los descuentos se aplican en el orden dado; con porcentajes, el orden no altera el resultado, pero se respeta para trazabilidad.
- `discounts` vacío equivale a factor `1` (sin descuento).
- `d ∈ [0, 100]`. Un descuento del `100%` deja el final a `0`.
- En `reverse`, un factor `0` (algún descuento del `100%`) es indeterminado → error `invalid_params`.
- Importes en `Decimal` con 2 decimales (`ROUND_HALF_UP`); porcentaje efectivo con 2 decimales.
- `discount_amount = |original − final|`.
- Calcula el descuento efectivo, no la suma aritmética: `10% + 5% = 14.50%` real.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field

class DiscountOperation(str, Enum):
    apply = "apply"
    reverse = "reverse"

class DiscountsInput(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    discounts: list[Decimal] = Field(default_factory=list, max_length=10)
    operation: DiscountOperation = DiscountOperation.apply
    currency: str = Field(default="EUR", min_length=3, max_length=3)

class DiscountsOutput(BaseModel):
    original_amount: Decimal
    final_amount: Decimal
    discount_amount: Decimal
    total_discount_pct: Decimal
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Dos descuentos | `amount=1000`, `discounts=[10,5]`, `apply` | original 1000.00, final 855.00, dto 145.00, pct 14.50 |
| Descuento único | `amount=200`, `discounts=[50]`, `apply` | final 100.00, pct 50.00 |
| Sin descuento | `amount=100`, `discounts=[]`, `apply` | original 100.00, final 100.00, pct 0.00 |
| Descuento total | `amount=100`, `discounts=[100]`, `apply` | final 0.00, pct 100.00 |
| Invertir dos | `amount=855`, `discounts=[10,5]`, `reverse` | original 1000.00, dto 145.00, pct 14.50 |
| Invertir uno | `amount=100`, `discounts=[20]`, `reverse` | original 125.00, dto 25.00, pct 20.00 |
| Invertir con 100% | `amount=100`, `discounts=[100]`, `reverse` | error `invalid_params` |
| Descuento inválido | `discounts=[101]` | error `invalid_params` |
| Importe negativo | `amount=-10` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": { "amount": "1000", "discounts": ["10", "5"], "operation": "apply" },
  "output": {
    "original_amount": "1000.00",
    "final_amount": "855.00",
    "discount_amount": "145.00",
    "total_discount_pct": "14.50",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "200", "discounts": ["50"], "operation": "apply" },
  "output": {
    "original_amount": "200.00",
    "final_amount": "100.00",
    "discount_amount": "100.00",
    "total_discount_pct": "50.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "855", "discounts": ["10", "5"], "operation": "reverse" },
  "output": {
    "original_amount": "1000.00",
    "final_amount": "855.00",
    "discount_amount": "145.00",
    "total_discount_pct": "14.50",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "100", "discounts": ["20"], "operation": "reverse" },
  "output": {
    "original_amount": "125.00",
    "final_amount": "100.00",
    "discount_amount": "25.00",
    "total_discount_pct": "20.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "100", "discounts": [], "operation": "apply" },
  "output": {
    "original_amount": "100.00",
    "final_amount": "100.00",
    "discount_amount": "0.00",
    "total_discount_pct": "0.00",
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
  "result_type": "calculation",
  "is_estimated": false,
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Usada por `procurement.compare_offers` para normalizar precios con descuentos.
- Combinada con `finance.margin` para validar que el precio final cubre el margen mínimo.
- Usada por `documents.generate_invoice` para líneas con descuento.

## 8. Decisiones pendientes

- ¿Soportar descuentos absolutos (€) mezclados con porcentuales? Propuesta: lista de objetos `{type, value}` en v1.1.
- ¿Devolver el desglose por tramo (`10% = 100 €`, `5% = 45 €`)? Propuesta: campo `breakdown` opcional.
- Redondeo intermedio por tramo vs. solo al final: se decide redondear solo al final (documentado).
