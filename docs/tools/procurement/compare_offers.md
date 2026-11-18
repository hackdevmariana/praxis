---
estado: MVP
version: 1.0.0
tool: procurement.compare_offers
---

# `procurement.compare_offers` — Comparación de ofertas

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `procurement.calculate` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (datos aportados por el usuario o extraídos de PDF) |
| Caché | n/a |
| Perfiles | `praxis-biz` (asociación) |

## 2. Semántica exacta

Normaliza entre 2 y 5 ofertas a un **coste total** comparable a `years` años (por defecto 5).

Precio mensual por año:

- Año 1: `monthly_price`.
- Año 2: `year2_price` si se aporta; si no, `monthly_price`.
- Año ≥ 3: `year3_price` si se aporta; si no, `year2_price`; si no, `monthly_price`.

Cálculo:

1. **Base imponible:** si `vat_included=true`, cada precio se divide por `1 + vat_rate/100` y se redondea a 2 decimales. La comparación se hace siempre sin IVA.
2. `recurring_cost = 12 × Σ precios mensuales de los N años`.
3. `one_off_cost = upfront_cost + cancellation_cost`.
4. `total_cost = recurring_cost + one_off_cost`.
5. `annual_cost = round(total_cost / years)`.
6. `monthly_cost = round(total_cost / (years × 12))`.

`cancelation_cost` se incluye como coste de riesgo (peor caso al no cumplir permanencia); no se descuenta.

Normalización (`normalize_by`) solo cambia la ordenación y la métrica destacada, no los cálculos:

| `normalize_by` | Métrica de ranking |
|---|---|
| `total_cost` (defecto) | `total_cost` |
| `annual` | `annual_cost` |
| `monthly` | `monthly_cost` |

Reglas:

- `years ∈ [1, 10]`.
- Todas las ofertas deben compartir `currency`; si no → error `currency_mismatch`.
- `permanence_months` es informativo (bloqueo contractual), no entra en el coste.
- Empates: se ordena por `supplier` ascendente.
- Con 2 ofertas se emite warning `few_offers`; con más de 5 → error `invalid_params`.
- Importes en `Decimal`, 2 decimales (`ROUND_HALF_UP`).
- `is_estimated=true`: los precios son aportados y pueden no incluir extras no declarados.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field

class NormalizeBy(str, Enum):
    total_cost = "total_cost"
    monthly = "monthly"
    annual = "annual"

class OfferInput(BaseModel):
    supplier: str = Field(min_length=1, max_length=120)
    monthly_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    permanence_months: int = Field(default=0, ge=0, le=120)
    cancellation_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    year2_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    year3_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    upfront_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    vat_included: bool = False
    vat_rate: Decimal = Field(default=Decimal("21"), ge=0, le=100)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

class CompareOffersInput(BaseModel):
    offers: list[OfferInput] = Field(min_length=2, max_length=5)
    years: int = Field(default=5, ge=1, le=10)
    normalize_by: NormalizeBy = NormalizeBy.total_cost

class OfferRow(BaseModel):
    supplier: str
    monthly_price_net: Decimal
    recurring_cost: Decimal
    one_off_cost: Decimal
    total_cost: Decimal
    annual_cost: Decimal
    monthly_cost: Decimal
    permanence_months: int
    rank: int
    is_cheapest: bool
    savings_vs_most_expensive: Decimal

class CompareOffersOutput(BaseModel):
    years: int
    normalize_by: NormalizeBy
    currency: str
    ranking: list[dict]
    normalized_table: list[OfferRow]
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Tres ofertas, 5 años | A 100/100/110 + 500 cancelación; B 90/95/100 + 1000; C 110 fijo + 200 alta | C 6800, B 6820, A 6860 |
| Orden por anual | mismo caso, `normalize_by=annual` | C, B, A (1360, 1364, 1372) |
| Dos ofertas | 2 ofertas | warning `few_offers` |
| Seis ofertas | 6 ofertas | error `invalid_params` |
| Divisa distinta | EUR y USD | error `currency_mismatch` |
| IVA incluido | `monthly_price=121`, `vat_included=true` | `monthly_price_net=100.00` |
| Descuento por volumen | año2/año3 más baratos | menor recurring_cost |
| Sin permanencia | `permanence_months=0` | informativo, coste igual |

## 5. Golden cases

```json
{
  "input": {
    "years": 5,
    "normalize_by": "total_cost",
    "offers": [
      { "supplier": "A", "monthly_price": "100", "permanence_months": 24, "cancellation_cost": "500", "year2_price": "100", "year3_price": "110" },
      { "supplier": "B", "monthly_price": "90", "permanence_months": 36, "cancellation_cost": "1000", "year2_price": "95", "year3_price": "100" },
      { "supplier": "C", "monthly_price": "110", "permanence_months": 0, "cancellation_cost": "0", "upfront_cost": "200" }
    ]
  },
  "output": {
    "years": 5,
    "normalize_by": "total_cost",
    "currency": "EUR",
    "ranking": [
      { "rank": 1, "supplier": "C", "total_cost": "6800.00" },
      { "rank": 2, "supplier": "B", "total_cost": "6820.00" },
      { "rank": 3, "supplier": "A", "total_cost": "6860.00" }
    ],
    "normalized_table": [
      { "supplier": "C", "monthly_price_net": "110.00", "recurring_cost": "6600.00", "one_off_cost": "200.00", "total_cost": "6800.00", "annual_cost": "1360.00", "monthly_cost": "113.33", "permanence_months": 0, "rank": 1, "is_cheapest": true, "savings_vs_most_expensive": "60.00" },
      { "supplier": "B", "monthly_price_net": "90.00", "recurring_cost": "5820.00", "one_off_cost": "1000.00", "total_cost": "6820.00", "annual_cost": "1364.00", "monthly_cost": "113.67", "permanence_months": 36, "rank": 2, "is_cheapest": false, "savings_vs_most_expensive": "40.00" },
      { "supplier": "A", "monthly_price_net": "100.00", "recurring_cost": "6360.00", "one_off_cost": "500.00", "total_cost": "6860.00", "annual_cost": "1372.00", "monthly_cost": "114.33", "permanence_months": 24, "rank": 3, "is_cheapest": false, "savings_vs_most_expensive": "0.00" }
    ]
  }
}
```

```json
{
  "input": {
    "years": 1,
    "offers": [
      { "supplier": "X", "monthly_price": "121", "vat_included": true, "vat_rate": "21" },
      { "supplier": "Y", "monthly_price": "105", "vat_included": false }
    ]
  },
  "output": {
    "ranking": [
      { "rank": 1, "supplier": "X", "total_cost": "1200.00" },
      { "rank": 2, "supplier": "Y", "total_cost": "1260.00" }
    ]
  },
  "metadata": { "warnings": ["few_offers", "mixed_vat_basis_normalized"] }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "user_input",
  "source_type": "user_input",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "comparison",
  "is_estimated": true,
  "confidence": 0.85,
  "currency": "EUR",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": true
}
```

## 7. Composiciones

- Usa `documents.extract_invoice` para convertir presupuestos PDF en `OfferInput`.
- Usa `currency.convert` si las ofertas llegan en divisas distintas (antes de llamar aquí).
- Alimenta `savings_ledger` (v2) y `rfp_generation` (v2).

## 8. Decisiones pendientes

- Pendiente: modelo de costes más rico (consumibles, formación, SLA, coste por usuario) en v1.1; decisión de producto.
- Decidido: sumar siempre el coste de cancelación como coste de riesgo; `permanence_months` informativo (implementado en v1).
- Pendiente: `total_cost_3y` / `total_cost_5y` simultáneos para comparar horizontes distintos; decisión de producto.
- Pendiente: verificar que `documents.extract_invoice` marca los importes con/sin IVA de forma fiable.
