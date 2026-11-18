---
estado: MVP
version: 1.0.0
tool: finance.margin
---

# `finance.margin` — Calcular margen y markup

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

Calcula margen (sobre precio de venta) y markup (sobre coste).

Definiciones:

- `margin_amount = price − cost`
- `margin_pct = margin_amount / price × 100` (margen comercial)
- `markup_pct = margin_amount / cost × 100` (margen sobre coste)

Se deben aportar **exactamente dos** de los tres valores `{cost, price, margin_pct}`:

| Dados | Se calcula |
|---|---|
| `cost`, `price` | `margin_amount`, `margin_pct`, `markup_pct` |
| `cost`, `margin_pct` | `price = cost / (1 − margin_pct/100)`, `markup_pct` |
| `price`, `margin_pct` | `cost = price × (1 − margin_pct/100)`, `markup_pct` |

Reglas:

- Importes en `Decimal` con 2 decimales (`ROUND_HALF_UP`); porcentajes con 2 decimales.
- `margin_pct` debe ser `< 100` siempre (restricción de esquema).
- `cost = 0` y `price > 0`: `markup_pct = null` y warning `markup_undefined` (división por cero).
- `price = 0` y `cost > 0`: `margin_pct = null` y warning `margin_undefined`; el resto de campos se calcula normalmente.
- `price = 0` y `cost = 0`: todo `0`; `margin_pct` y `markup_pct` se devuelven `0`.
- Se permiten valores negativos (pérdidas): `margin_pct` puede ser negativo; `markup_pct` puede ser `null` cuando no está definido.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

class MarginInput(BaseModel):
    cost: Decimal | None = Field(default=None, max_digits=16, decimal_places=2)
    price: Decimal | None = Field(default=None, max_digits=16, decimal_places=2)
    margin_pct: Decimal | None = Field(default=None, lt=100)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    @model_validator(mode="after")
    def exactamente_dos(self):
        dados = sum(v is not None for v in (self.cost, self.price, self.margin_pct))
        if dados != 2:
            raise ValueError("Aporta exactamente dos de {cost, price, margin_pct}")
        return self

class MarginOutput(BaseModel):
    cost: Decimal | None
    price: Decimal | None
    margin_amount: Decimal
    margin_pct: Decimal | None
    markup_pct: Decimal | None
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Coste y precio | `cost=100`, `price=150` | margin 50.00, margin_pct 33.33, markup 50.00 |
| Coste y margen | `cost=100`, `margin_pct=40` | price 166.67, margin 66.67, markup 66.67 |
| Precio y margen | `price=100`, `margin_pct=30` | cost 70.00, margin 30.00, markup 42.86 |
| Sin beneficio | `cost=100`, `price=100` | margin 0.00, pcts 0.00 |
| Pérdida | `cost=100`, `price=80` | margin −20.00, margin_pct −25.00, markup −20.00 |
| Coste cero | `cost=0`, `price=50` | margin 50.00, margin_pct 100.00, markup null |
| Margen ≥ 100 | `cost=100`, `margin_pct=100` | error `invalid_params` |
| Un solo dato | `cost=100` | error `invalid_params` |
| Tres datos | `cost=100`, `price=150`, `margin_pct=40` | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": { "cost": "100", "price": "150" },
  "output": {
    "cost": "100.00",
    "price": "150.00",
    "margin_amount": "50.00",
    "margin_pct": "33.33",
    "markup_pct": "50.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "cost": "100", "margin_pct": "40" },
  "output": {
    "cost": "100.00",
    "price": "166.67",
    "margin_amount": "66.67",
    "margin_pct": "40.00",
    "markup_pct": "66.67",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "price": "100", "margin_pct": "30" },
  "output": {
    "cost": "70.00",
    "price": "100.00",
    "margin_amount": "30.00",
    "margin_pct": "30.00",
    "markup_pct": "42.86",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "cost": "100", "price": "80" },
  "output": {
    "cost": "100.00",
    "price": "80.00",
    "margin_amount": "-20.00",
    "margin_pct": "-25.00",
    "markup_pct": "-20.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "cost": "0", "price": "50" },
  "output": {
    "cost": "0.00",
    "price": "50.00",
    "margin_amount": "50.00",
    "margin_pct": "100.00",
    "markup_pct": null,
    "currency": "EUR"
  },
  "metadata": { "warnings": ["markup_undefined"] }
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

- Base de `sim.hiring_simulator` (v2) para calcular el margen que aporta un comercial.
- Usada por `procurement.*` para evaluar ofertas y descuentos.
- Relacionada con `finance.discounts` (precio original vs. margen mínimo).

## 8. Decisiones pendientes

- Decidido: `markup_pct` como entrada válida en v1.1 (`{cost, markup_pct}` y `{price, markup_pct}`).
- Decidido: tool `finance.gross_margin` en v2 para distinguir margen bruto de comercial.
- Implementado: `price=0, cost>0` devuelve `margin_pct=null` con warning `margin_undefined`; `cost=0, price>0` devuelve `markup_pct=null` con warning `markup_undefined`.
