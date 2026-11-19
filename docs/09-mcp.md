---
estado: MVP
version: 0.1.0
---

# Especificación MCP

PRAXIS expone sus herramientas mediante el **Model Context Protocol**. El MCP es la interfaz primaria: cualquier agente compatible (Claude, GPT, Gemini, agentes locales con Ollama) puede consumir las herramientas sin configuración específica.

## Transporte

- **MCP sobre HTTP** (streamable HTTP) para uso remoto, servido por FastAPI.
- **stdio** *(planificado)*: el SDK lo soporta, pero la app no expone hoy un entrypoint stdio (`app/main.py` monta solo streamable HTTP en `/mcp`).
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

### Implementación MVP (inyectable)

- `app/tenancy.py` define `TenantProfile`, `ToolAccessPolicy`, `InMemoryToolAccessPolicy` y `SqlAlchemyToolAccessPolicy`.
- El catálogo se resuelve por `catalog_key` (`hotel`, `poligono`, `asociacion`, `general`) y se intersecta con `TenantProfile.enabled_tools` si está definido.
- `ToolContext.allowed_tools` transporta el resultado; el ejecutor devuelve `tool_not_available` si la tool no está permitida.
- `PraxisMCPServer.list_tools` (`app/mcp_server.py`, subclase de `MCPServer`) filtra el anuncio con el mismo contexto autenticado, de modo que el agente no ve tools fuera de su perfil.
- En el MVP los scopes del JWT/API key representan los `Permission` del rol. Sin `TenantProfile` para una empresa autenticada, el toolset es vacío (deny by default).
- Con `DATABASE_URL`, `TenantProfile`/`ToolActivation` se resuelven bajo RLS con `SqlAlchemyToolAccessPolicy`. Sin DB y sin política inyectada, `create_app` usa `AllowAllToolAccess` (desarrollo); se puede inyectar `InMemoryToolAccessPolicy` u otra `ToolAccessPolicy` en tests/arranque.
- Pendiente: overrides de catálogo y permisos por rol en base de datos.

## Autenticación y autorización

- **MVP implementado:** API key o JWT simple.
  - `Authorization: Bearer <jwt>`: HS256 con `sub`, `company_id`, `role`, `scopes`, `iat`, `exp`, `iss` y `aud`; expiración máxima de 30 minutos por defecto.
  - `X-API-Key: <key_id>.<secret>`: se localiza por prefijo y se valida contra su hash Argon2id (`PRAXIS_API_KEYS_FILE`).
  - `X-PRAXIS-Confirm: true`: señal de confirmación para tools con efectos.
- **Contexto:** `ToolContext` se construye desde la credencial; nunca se acepta `company_id` del cliente. El ejecutor comprueba scopes y confirmación antes de llamar al handler.
- **Modo desarrollo:** con `PRAXIS_AUTH_REQUIRED=false` se usa un contexto local con scope `*`; en producción debe estar activo y un scope `*` firmado se rechaza.
- **HTTP:** credenciales ausentes o inválidas devuelven `401` con `{ "success": false, "error": { "code", "message" } }`. `/health` es público.
- **OAuth 2.1** (`authlib`) para el servidor MCP se evalúa en v2; no se usa `python-jose`.

## Idempotencia y efectos

- Tools de solo lectura: `idempotentHint: true`, sin efectos.
- Tools con efectos (`calendar.create_event`, `documents.generate_invoice`, `alerts.contract_renewal`): requieren `idempotency_key`; el ejecutor deduplica por (`tool`, `company_id`, `idempotency_key`) antes de llamar al handler y guarda el resultado solo si tiene éxito.
- La misma clave con distinto `input_hash` devuelve `conflict`. `alerts.contract_renewal` añade un alias por `(contract_id, renewal_date)` para deduplicar reglas equivalentes con claves distintas.
- `destructiveHint` se marca en tools que modifican datos existentes.
- El servidor MCP puede exigir confirmación humana antes de ejecutar tools con `requires_confirmation`.

## Respuesta MCP

Se devuelve el sobre descrito en [`08-formatting.md`](08-formatting.md):

- `content`: JSON serializado (texto estructurado) para el agente.
- Metadatos accesibles para trazabilidad.
- *(Planificado)* En modo `compact` se omitiría lo prescindible para ahorrar tokens; hoy se devuelve siempre el sobre JSON completo.

Errores MCP:

| Código | Situación |
|---|---|
| `invalid_params` | `ToolError(INVALID_PARAMS)` lanzado al ejecutar; el rechazo de esquema previo lo gestiona el framework |
| `incompatible_units` | Unidades de dimensiones distintas en `units.convert` |
| `unsupported_currency` | Divisa fuera de la cesta de referencia del BCE |
| `currency_mismatch` | Ofertas con divisas distintas en `procurement.compare_offers` |
| `invalid_tax_id` | CIF/NIF español inválido en factura |
| `conflict` | Número de documento duplicado o idempotency_key reutilizada con otro input |
| `document_not_found` | Documento inexistente o de otro tenant |
| `unsupported_format` | Documento que no es un PDF legible |
| `document_too_large` | Documento por encima del límite |
| `authentication_required` | Faltan credenciales (HTTP 401) |
| `invalid_token` | JWT/API key inválidos o caducados (HTTP 401) |
| `permission_denied` | Scope insuficiente |
| `tool_not_available` | No activa para el tenant |
| `confirmation_required` | Efecto sin confirmación |
| `connector_not_connected` | El usuario no ha conectado el proveedor |
| `connector_auth_expired` | Token caducado o revocado |
| `contract_not_found` | Contrato inexistente o de otro tenant |
| `provider_unavailable` | API externa y fallback agotados |
| `rate_limited` | Límite de uso superado |
| `internal_error` | Fallo no controlado |

## Nombres y versiones

- `name`: estable y con namespace (`dominio.accion`).
- La versión viaja en el sobre (`tool_version`), no en el nombre anunciado.
- La deprecación se registra en `tool_activations.deprecated`/`replaced_by` y ya excluye la tool del toolset del tenant; el anuncio MCP con flags de deprecación requiere soporte futuro (ver [`17-versioning.md`](17-versioning.md)).

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
