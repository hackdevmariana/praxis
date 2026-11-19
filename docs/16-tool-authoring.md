---
estado: MVP
version: 0.1.0
---

# Guía para crear herramientas

Esta guía permite a contribuidores externos añadir herramientas a PRAXIS sin romper la coherencia del sistema. La licencia es MIT.

## Antes de empezar

Comprueba:

1. La herramienta **no** está en el catálogo ni en el backlog ([`03-tools-catalog.md`](03-tools-catalog.md)).
2. Cumple los **criterios de entrada** ([`02-mvp-scope.md`](02-mvp-scope.md#criterios-de-entrada-para-herramientas-de-backlog)).
3. La lógica es determinista o se apoya en una fuente externa verificable. **No** usa un LLM para producir el resultado.

## Estructura

```txt
app/tools/<dominio>/<tool>/
├── __init__.py
├── tool.py         # @tool + implementación
└── schemas.py      # Pydantic input/output

tests/
└── test_<dominio>_<tool>.py  # suites centralizadas en tests/
```

Formatters, si aplican, viven **fuera** del core (capa de canal); la tool no genera texto humano.

## Definición con `@tool`

```python
from app.context import ToolContext
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.vat.schemas import VatInput, VatOutput

@tool(
    name="finance.vat",
    version="1.0.0",
    title="Calcular IVA",
    permissions=["finance.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Suma, extrae o resta IVA de un importe con redondeo al céntimo. "
        "No usar para IRPF, impuesto de sociedades ni retenciones."
    ),
)
async def calculate_vat(params: VatInput, ctx: ToolContext) -> ToolResult[VatOutput]:
    ...
    return tool_result(VatOutput(...))
```

Reglas del decorador:

- `name`: `<dominio>.<accion>`, estable.
- `version`: SemVer (ver [`17-versioning.md`](17-versioning.md)).
- `permissions`: scopes requeridos.
- `data_classification`: `public | business | personal | sensitive`.
- `read_only`, `idempotent`, `requires_confirmation`.
- `mcp_description`: verbo + caso de uso + cuándo **no** usar.

De la definición se generan `inputSchema`, `outputSchema` y anotaciones MCP. La documentación y los golden tests se mantienen junto al código.

## Dinero y precisión

- Usa `Decimal` para importes; nunca `float`.
- Redondea con `ROUND_HALF_UP` a 2 decimales al final.
- No se usa `numpy-financial` en el MVP; si se incorpora, documenta el boundary `Decimal → float → Decimal` y añade test de cuadre al céntimo.
- Serializa importes como string en JSON.

## Metadatos

Toda salida se envuelve con el sobre común. Los metadatos base los construye el ejecutor con `app.metadata.build_metadata(...)`; la tool puede aportar `warnings`, `summary` y `metadata_extra` vía `ToolResult`:

- `source`, `source_type`, `retrieved_at`, `valid_until`.
- `is_estimated`, `confidence` (si aplica).
- `unit`, `currency`, `timezone`.
- `warnings`, `errors`, `legal_disclaimer_required`.

No construyas el sobre a mano si existe el helper común.

## Proveedores externos

Si la tool consulta una API:

1. Añade una **ficha de proveedor** YAML (ver [`06-external-apis.md`](06-external-apis.md)).
2. Usa `httpx` con timeouts; reintentos con `stamina` son objetivo pendiente de estandarizar.
3. Respeta rate limits y define caché por `valid_until`.
4. Declara `fallback_providers` y circuit breaker.
5. No incluyas claves; se leen de `.env`.
6. Añade tests con `respx` (éxito, timeout, 429, 5xx, fallback).

## Tests obligatorios

- Caso feliz con salida exacta.
- Caso límite (cero, negativos, redondeos, límites).
- Caso de error (entrada inválida, proveedor caído, permiso insuficiente).
- Propiedades con `Hypothesis` si hay invariantes matemáticos.
- Aislamiento si toca datos de tenant (testcontainers + RLS).

## Seguridad

- No loguees datos personales ni credenciales.
- Si la tool escribe, declara `idempotent` y `requires_confirmation` cuando proceda.
- Si trata datos personales/sensibles, documenta el cifrado y los permisos.
- No aceptes `company_id` del cliente sin validarlo contra el token.

## Documentación

- Añade la tool a [`03-tools-catalog.md`](03-tools-catalog.md) con su ficha.
- Actualiza `intents.yaml` si aplica (v2).
- Incluye ejemplos de entrada/salida en `mcp_description` o `examples`.
- Registra la decisión si afecta a la arquitectura (ADR).

## Checklist de PR

- [ ] Criterios de entrada cumplidos.
- [ ] `@tool` con todos los flags y permisos.
- [ ] Esquemas Pydantic de entrada y salida.
- [ ] Metadatos completos vía helper.
- [ ] Golden tests (feliz, límite, error) y propiedades.
- [ ] Tests de proveedor con `respx` (si aplica).
- [ ] Ficha de proveedor (si aplica).
- [ ] Sin claves ni datos personales en logs.
- [ ] Documentación y catálogo actualizados.
- [ ] `ruff`, `pyright` y `pytest` en verde.
- [ ] Versión y notas de cambio.

## Revisión

Un mantenedor verifica:

- Determinismo y ausencia de LLM en el cálculo.
- Trazabilidad y metadatos.
- Cumplimiento de licencias y términos de las fuentes.
- Impacto en aislamiento multi-tenant.
