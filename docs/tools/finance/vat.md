---
estado: MVP
version: 1.0.0
tool: finance.vat
---

# `finance.vat` — Calcular IVA

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

Suma, extrae o resta IVA de un importe. Todos los importes son `Decimal` y se redondean con `ROUND_HALF_UP` a 2 decimales.

| `operation` | `amount` representa | Cálculo |
|---|---|---|
| `add` | Base imponible | `vat = round(base × rate / 100)`, `total = base + vat` |
| `extract` | Importe **con** IVA | `base = round(total / (1 + rate/100))`, `vat = total − base` |
| `remove` | Importe **con** IVA | Igual que `extract`; alias semántico («quitar el IVA»), enfatiza la base |

Reglas:

- En `add`, `base_amount = amount` y `total_amount = amount + vat_amount`.
- En `extract`/`remove`, `total_amount = amount` y `vat_amount = total_amount − base_amount`, de modo que **base + IVA = total** exactamente al céntimo.
- `rate` admite `0` (exento) y hasta `100`.
- `amount` admite `0` (devuelve todo a cero); no admite negativos.
- No se infiere el tipo de IVA por producto: lo aporta el llamador o `praxis-knowledge` (tipos vigentes versionados en `TaxRate`).
- Importes devueltos como **string decimal** en JSON.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field

class VatOperation(StrEnum):
    add = "add"
    extract = "extract"
    remove = "remove"

class VatInput(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    rate: Decimal = Field(default=Decimal("21"), ge=0, le=100)
    operation: VatOperation = VatOperation.add
    currency: str = Field(default="EUR", min_length=3, max_length=3)

class VatOutput(BaseModel):
    base_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Sumar IVA 21% | `amount=1000`, `rate=21`, `operation=add` | base 1000.00, vat 210.00, total 1210.00 |
| Sumar IVA con céntimos | `amount=99.99`, `rate=21`, `add` | base 99.99, vat 21.00, total 120.99 |
| Extraer IVA | `amount=1210`, `rate=21`, `extract` | base 1000.00, vat 210.00, total 1210.00 |
| Extraer con céntimos | `amount=120.99`, `rate=21`, `extract` | base 99.99, vat 21.00, total 120.99 |
| Restar IVA | `amount=1210`, `rate=21`, `remove` | base 1000.00, vat 210.00 |
| IVA reducido 10% | `amount=50`, `rate=10`, `add` | vat 5.00, total 55.00 |
| IVA superreducido 4% | `amount=100`, `rate=4`, `add` | vat 4.00, total 104.00 |
| Exento | `amount=100`, `rate=0`, `add` | vat 0.00, total 100.00 |
| Cero | `amount=0`, `rate=21`, `add` | todo 0.00 |
| Redondeo | `amount=0.01`, `rate=21`, `add` | vat 0.00, total 0.01 |
| Importe negativo | `amount=-5` | rechazo de esquema (`422` en REST; error de tool en MCP) |
| Tipo fuera de rango | `rate=101` | rechazo de esquema (`422` en REST; error de tool en MCP) |

Los fallos de esquema se rechazan antes de ejecutar la tool, así que no viajan en el sobre.

## 5. Golden cases

```json
{
  "input": { "amount": "1000", "rate": "21", "operation": "add" },
  "output": {
    "base_amount": "1000.00",
    "vat_rate": "21",
    "vat_amount": "210.00",
    "total_amount": "1210.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "99.99", "rate": "21", "operation": "add" },
  "output": {
    "base_amount": "99.99",
    "vat_rate": "21",
    "vat_amount": "21.00",
    "total_amount": "120.99",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "1210", "rate": "21", "operation": "extract" },
  "output": {
    "base_amount": "1000.00",
    "vat_rate": "21",
    "vat_amount": "210.00",
    "total_amount": "1210.00",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "120.99", "rate": "21", "operation": "remove" },
  "output": {
    "base_amount": "99.99",
    "vat_rate": "21",
    "vat_amount": "21.00",
    "total_amount": "120.99",
    "currency": "EUR"
  }
}
```

```json
{
  "input": { "amount": "100", "rate": "4", "operation": "add" },
  "output": {
    "base_amount": "100.00",
    "vat_rate": "4",
    "vat_amount": "4.00",
    "total_amount": "104.00",
    "currency": "EUR"
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

- Base de `documents.generate_invoice` (IVA por línea y total).
- Usada por `procurement.compare_offers` para homogeneizar importes con/sin IVA.
- Los tipos vigentes se consultan en `TaxRate` (global, versionado), no se codifican aquí.

## 8. Decisiones pendientes

- ¿Soportar importes con más de 2 decimales (precios unitarios) y redondear solo en el total? Propuesta: parámetro `rounding` en v1.1.
- ¿Añadir `operation=breakdown` para devolver el desglose por tipo en una factura? Propuesta: tool `finance.vat_breakdown` en v2.
- `extract` y `remove` son equivalentes; mantener ambos por compatibilidad semántica.
