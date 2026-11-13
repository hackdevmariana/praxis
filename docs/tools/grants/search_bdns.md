---
estado: backlog
version: 0.1.0
tool: grants.search_bdns
---

# `grants.search_bdns` — Búsqueda de subvenciones (BDNS)

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `grants.read` |
| Clasificación | `business` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | API pública de la BDNS (MITES) |
| Caché | 12 h |

## 2. Semántica exacta

Busca subvenciones públicas en la Base de Datos Nacional de Subvenciones.

- Filtros combinables: texto libre (`query` sobre título y descripción, sin distinguir mayúsculas ni acentos), CNAE (prefijo de 4 dígitos), provincia, importe mínimo/máximo y fecha límite mínima.
- **Solapamiento de importes:** una ayuda entra si `amount_max ≥ min_amount` y `amount_min ≤ max_amount` (cuando se aportan).
- `status`: `open` si `deadline ≥ hoy`, `closed` si ya pasó; `deadline=null` se trata como `open` con warning `no_deadline`.
- Orden por defecto: `deadline` ascendente (sin fecha al final), desempate por `grant_id`. Alternativas: `amount_asc`, `amount_desc`, `relevance`.
- Paginación determinista: `page` desde 1, `page_size` 20 por defecto.
- Se deduplican convocatorias por `grant_id`.

Reglas:

- `query` ≤ 300 caracteres; `province` nombre oficial; `cnae` 4 dígitos.
- `min_amount ≤ max_amount` si ambos se aportan.
- Importes 2 decimales; el importe puede ser `null` si la convocatoria no lo publica.
- `dataset_version` identifica el snapshot de la BDNS usado.

## 3. Contrato Pydantic

```python
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class GrantsSort(str, Enum):
    deadline = "deadline"
    amount_asc = "amount_asc"
    amount_desc = "amount_desc"
    relevance = "relevance"

class GrantsSearchInput(BaseModel):
    query: str | None = Field(default=None, max_length=300)
    cnae: str | None = Field(default=None, pattern=r"^\d{4}$")
    province: str | None = Field(default=None, max_length=80)
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    deadline_after: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: GrantsSort = GrantsSort.deadline

    @model_validator(mode="after")
    def importes(self):
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            raise ValueError("min_amount no puede superar a max_amount")
        return self

class GrantItem(BaseModel):
    grant_id: str
    title: str
    organ: str
    amount_min: Decimal | None
    amount_max: Decimal | None
    deadline: date | None
    cnae: list[str]
    province: str | None
    url: str
    status: str  # open | closed

class GrantsSearchOutput(BaseModel):
    results: list[GrantItem]
    total: int
    page: int
    page_size: int
    dataset_version: str
    retrieved_at: datetime
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Búsqueda digitalización | `query=digitalización`, CNAE 5610, Madrid, ≥ 5.000 € | 2 resultados |
| Texto sin acentos | `query=digitalizacion` | mismos resultados |
| Sin resultados | combinación imposible | `results=[]`, `total=0` |
| Solo abiertas | `deadline_after=2026-11-13` | excluye cerradas |
| Orden por importe | `sort=amount_desc` | mayor importe primero |
| Paginación | `page=2`, `page_size=1` | segundo resultado |
| Rango inválido | `min_amount > max_amount` | error `invalid_params` |
| CNAE inválido | `cnae=56` | error `invalid_params` |
| BDNS caída | timeout del proveedor | error `provider_unavailable` |

## 5. Decisiones pendientes

- Alertas de nuevas convocatorias por perfil de empresa.
- Requisitos de elegibilidad y documentación (no solo metadatos).
- Subvenciones autonómicas y locales fuera de BDNS.
- Detección de duplicados entre administraciones.
- Promover a spec completa cuando entre en el MVP.
