---
estado: MVP
version: 0.1.0
---

# Especificación MCP

PRAXIS expone sus herramientas mediante el **Model Context Protocol**. El MCP es la interfaz primaria: cualquier agente compatible (Claude, GPT, Gemini, agentes locales con Ollama) puede consumir las herramientas sin configuración específica.

## Transporte

- **MCP sobre HTTP** (streamable HTTP) para uso remoto, servido por FastAPI.
- **stdio** para uso local en agentes de escritorio.
- Implementación con el SDK oficial `mcp` y transporte streamable HTTP.
- El servidor MCP se monta en `app/main.py` en `/mcp`, junto a `/health` y las rutas REST auxiliares.
- `fastapi-mcp` se evaluó, pero su versión 0.4 no es compatible con `mcp` 2.x; el registro se expone directamente con el SDK.

## Descubrimiento de tools

Cada tool declara:

- `name` (p. ej. `finance.vat`) y `title` legible.
- `description` rica para el agente, con cuándo usarla y cuándo no.
- `inputSchema` / `outputSchema` generados desde Pydantic.
- `examples` de entrada/salida (few-shot para el agente).
- Anotaciones: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`.

El catálogo se genera desde el registro de tools en código (ADR-004); la BD solo añade overrides por tenant.

## Toolsets por TenantProfile

El agente **no recibe todas las herramientas**, sino solo las relevantes para su función, permisos y contexto. Esto reduce ruido, errores de selección y tokens.

| `catalog_key` | Tools principales |
|---|---|
| `hotel` | `datetime.*`, `finance.vat`, `weather.forecast`, `geo.geocode`, `calendar.*`, `documents.*`, `currency.convert` |
| `poligono` | `finance.*`, `validate.*`, `units.convert`, `weather.forecast`, `geo.geocode`, `documents.*`, `procurement.*`, `alerts.contract_renewal` |
| `asociacion` | `procurement.*`, `finance.*`, `validate.*`, `documents.*`, `alerts.contract_renewal`, `currency.convert` |
| `general` | Todas las deterministas + externas básicas |

Reglas:

- El toolset efectivo = intersección de (`TenantProfile.catalog`, `Permission` del rol, `ToolActivation.is_enabled`).
- Las tools no activas no se anuncian; si se invocan, el servidor responde `tool_not_available`.
- `ToolCatalog` permite catálogos personalizados por tenant en el futuro (base para planes SaaS).

## Autenticación y autorización

- **MVP:** API key + JWT simple.
  - La API key identifica la instalación/usuario y se valida con hash Argon2id.
  - El JWT aporta `sub`, `company_id`, `role`, `scopes`.
- **OAuth 2.1** (`authlib`) para el servidor MCP se evalúa en v2; no se usa `python-jose`.
- El contexto de ejecución (`ToolContext`) se construye a partir del token y nunca se acepta `company_id` del cliente sin validarlo contra el token.

## Idempotencia y efectos

- Tools de solo lectura: `idempotentHint: true`, sin efectos.
- Tools con efectos (`calendar.create_event`, `documents.generate_invoice`, `alerts.contract_renewal`): requieren `idempotency_key`; el servidor deduplica por (`tool`, `company_id`, `idempotency_key`).
- `destructiveHint` se marca en tools que modifican datos existentes.
- El servidor MCP puede exigir confirmación humana antes de ejecutar tools con `requires_confirmation`.

## Respuesta MCP

Se devuelve el sobre descrito en [`08-formatting.md`](08-formatting.md):

- `content`: JSON serializado (texto estructurado) para el agente.
- Metadatos accesibles para trazabilidad.
- En modo `compact`, se omite lo prescindible para ahorrar tokens.

Errores MCP:

| Código | Situación |
|---|---|
| `invalid_params` | `ToolError(INVALID_PARAMS)` lanzado al ejecutar; el rechazo de esquema previo lo gestiona el framework |
| `incompatible_units` | Unidades de dimensiones distintas en `units.convert` |
| `unsupported_currency` | Divisa fuera de la cesta de referencia del BCE |
| `permission_denied` | Scope insuficiente |
| `tool_not_available` | No activa para el tenant |
| `confirmation_required` | Efecto sin confirmación |
| `provider_unavailable` | API externa y fallback agotados |
| `rate_limited` | Límite de uso superado |
| `internal_error` | Fallo no controlado |

## Nombres y versiones

- `name`: estable y con namespace (`dominio.accion`).
- La versión viaja en el sobre (`tool_version`), no en el nombre anunciado.
- Herramientas deprecadas se mantienen anunciadas con `deprecated: true` y `replaced_by` hasta su retirada (ver [`17-versioning.md`](17-versioning.md)).

## Ejemplo de definición (conceptual)

```python
@tool(
    name="finance.vat",
    version="1.0.0",
    permissions=["finance.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    mcp_description=(
        "Calcula IVA español. Usar para sumar, extraer o restar IVA de un importe. "
        "No usar para IRPF ni impuesto de sociedades."
    ),
)
async def calculate_vat(params: VatInput, ctx: ToolContext) -> VatOutput: ...
```

De esta definición se generan `inputSchema`, `outputSchema`, anotaciones MCP, documentación y golden tests.

## Buenas prácticas de descripción

- Empezar por el verbo y el caso de uso principal.
- Indicar explícitamente **cuándo no usar** la tool.
- Describir unidades y monedas esperadas en la entrada.
- Mantener descripciones cortas pero ricas: son el principal ahorro/error de selección del agente.
- No incluir instrucciones de negocio que cambien con el tiempo: eso vive en `praxis-knowledge`.

Ver también [`03-tools-catalog.md`](03-tools-catalog.md) para el contrato de cada tool del MVP.
