---
estado: v2
version: 0.1.0
tool: procurement.detect_price_increase
---

# `procurement.detect_price_increase` — Subidas de precio anómalas

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `procurement.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (datos aportados) |
| Caché | n/a |
| Perfiles | `praxis-biz` (asociación) |

## 2. Semántica exacta

Detecta subidas de precio de compra respecto al precio anterior.

Por ítem:

- `change_amount = current_unit_price − previous_unit_price`.
- `change_pct = change_amount / previous_unit_price × 100` (si `previous_unit_price > 0`; si no, `null` y `is_new_price=true`).
- `annual_impact = change_amount × annual_quantity` si se aporta `annual_quantity`.
- `is_anomalous = change_pct ≥ threshold_pct`.
- Severidad: `high` si `change_pct ≥ 2 × threshold_pct`; `medium` si `≥ threshold_pct`; `low` en el resto. `new_price` si no hay precio previo.

Reglas:

- `previous_unit_price ≥ 0`, `current_unit_price ≥ 0`, `annual_quantity ≥ 0`.
- `threshold_pct > 0` (por defecto `10`).
- Las bajadas de precio no son anomalía (`change_pct` negativo, severidad `low`).
- Orden de salida: por `change_pct` descendente (los `null` al final), luego por descripción.
- Importes 2 decimales; porcentajes 2.
- `is_estimated=true`: la anomalía depende del umbral aportado, no de un modelo estadístico.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class PriceItem(BaseModel):
    supplier: str
    product_code: str | None = None
    description: str
    previous_unit_price: Decimal = Field(ge=0)
    current_unit_price: Decimal = Field(ge=0)
    previous_date: str | None = None
    current_date: str | None = None
    annual_quantity: Decimal | None = Field(default=None, ge=0)

class PriceIncreaseInput(BaseModel):
    items: list[PriceItem] = Field(min_length=1, max_length=500)
    threshold_pct: Decimal = Field(default=Decimal("10"), gt=0, le=100)

class PriceAlert(BaseModel):
    supplier: str
    product_code: str | None
    description: str
    previous_unit_price: Decimal
    current_unit_price: Decimal
    change_amount: Decimal
    change_pct: Decimal | None
    annual_impact: Decimal | None
    is_new_price: bool
    is_anomalous: bool
    severity: str  # high | medium | low | new_price

class PriceIncreaseOutput(BaseModel):
    alerts: list[PriceAlert]
    anomalous_count: int
    high_count: int
    medium_count: int
    new_price_count: int
    currency: str
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Subida normal | 10 → 10,5 (+5%) | no anómala, `low` |
| Subida media | 20 → 24 (+20%, umbral 10%) | `high` (≥ 2×) |
| Subida fuerte | 5 → 6,5 (+30%) | `high` |
| Bajada | 20 → 18 (−10%) | `low`, no anómala |
| Producto nuevo | previo 0 → 3 | `new_price`, `change_pct=null` |
| Sin cantidad | sin `annual_quantity` | `annual_impact=null` |
| Umbral 0 | `threshold_pct=0` | error `invalid_params` |
| Importe negativo | precio −1 | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": {
    "threshold_pct": "10",
    "items": [
      { "supplier": "Molinos S.A.", "product_code": "HAR-01", "description": "Harina", "previous_unit_price": "10", "current_unit_price": "10.5", "annual_quantity": "12000" },
      { "supplier": "Aceites S.L.", "product_code": "ACE-02", "description": "Aceite", "previous_unit_price": "20", "current_unit_price": "24", "annual_quantity": "5000" },
      { "supplier": "Limpia S.L.", "product_code": "DET-03", "description": "Detergente", "previous_unit_price": "5", "current_unit_price": "6.5", "annual_quantity": "2000" },
      { "supplier": "Nuevo S.L.", "product_code": "NEW-04", "description": "Producto nuevo", "previous_unit_price": "0", "current_unit_price": "3" }
    ]
  },
  "output": {
    "anomalous_count": 2,
    "high_count": 2,
    "medium_count": 0,
    "new_price_count": 1,
    "currency": "EUR",
    "alerts": [
      { "supplier": "Limpia S.L.", "product_code": "DET-03", "description": "Detergente", "previous_unit_price": "5.00", "current_unit_price": "6.50", "change_amount": "1.50", "change_pct": "30.00", "annual_impact": "3000.00", "is_new_price": false, "is_anomalous": true, "severity": "high" },
      { "supplier": "Aceites S.L.", "product_code": "ACE-02", "description": "Aceite", "previous_unit_price": "20.00", "current_unit_price": "24.00", "change_amount": "4.00", "change_pct": "20.00", "annual_impact": "20000.00", "is_new_price": false, "is_anomalous": true, "severity": "high" },
      { "supplier": "Molinos S.A.", "product_code": "HAR-01", "description": "Harina", "previous_unit_price": "10.00", "current_unit_price": "10.50", "change_amount": "0.50", "change_pct": "5.00", "annual_impact": "6000.00", "is_new_price": false, "is_anomalous": false, "severity": "low" },
      { "supplier": "Nuevo S.L.", "product_code": "NEW-04", "description": "Producto nuevo", "previous_unit_price": "0.00", "current_unit_price": "3.00", "change_amount": "3.00", "change_pct": null, "annual_impact": null, "is_new_price": true, "is_anomalous": false, "severity": "new_price" }
    ]
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
  "result_type": "analysis",
  "is_estimated": true,
  "confidence": 0.9,
  "currency": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": false
}
```

## 7. Composiciones

- Usa `documents.extract_invoice` para obtener precios de facturas de compra.
- Alimenta `procurement.savings_ledger` con el impacto anual detectado.
- Base de `alerts.*` para avisar al comprador.

## 8. Decisiones pendientes

- Pendiente: detección estadística (media/mediana histórica, z-score) además del umbral fijo; decisión de producto.
- Pendiente: comparación entre proveedores para el mismo producto; decisión de producto.
- Pendiente: estacionalidad y variaciones de materia prima (índices públicos); dataset.
