---
estado: MVP
version: 0.1.0
---

# Arquitectura

## Resumen

PRAXIS se organiza en **cuatro verticales** y **tres capas**. La regla central es separar la ejecución determinista de herramientas de cualquier lógica conversacional o de enrutamiento.

```txt
                 ┌──────────────────────────────────────────┐
                 │        Arnés del cliente (LLM)            │
                 │  Claude · GPT · Gemini · Ollama · bots    │
                 └───────────────┬──────────────────────────┘
                                 │ MCP (tools tipadas)
                 ┌───────────────▼──────────────────────────┐
                 │              praxis-core                  │
                 │   @tool · schemas · providers · metadata  │
                 │              (stateless)                   │
                 └───────┬───────────────┬──────────────────┘
                         │               │
        ┌────────────────▼───┐   ┌───────▼────────────────┐
        │  praxis-knowledge  │   │      praxis-biz         │
        │  (RAG / pgvector)  │   │ conectores · ingesta ·  │
        │  + second-brain    │   │ caché operacional       │
        └────────────────────┘   └─────────────────────────┘
                         │
                 ┌───────▼────────┐
                 │   praxis-sim   │
                 │  pipelines     │
                 └────────────────┘

    Capa de canal (externa, no incluida en core):
    WhatsApp/Telegram → gateway → semantic-router/regex → praxis-core
                               → formatters (texto humano)
```

## Las cuatro verticales

| Vertical | Estado | Responsabilidad | Límite |
|---|---|---|---|
| `praxis-core` | Casi stateless | Herramientas deterministas, providers, metadatos, servidor MCP. | No NLP, no routing, no formateo conversacional. |
| `praxis-knowledge` | Con estado | Conocimiento compartido y por empresa; búsqueda híbrida (FTS + pgvector); vigencia y citas. | No ejecuta cálculos operativos. |
| `praxis-biz` | Con estado (tenant) | Conectores, ingesta documental, caché operacional, datos de la empresa. | No es ERP maestro. |
| `praxis-sim` | Pipelines | Compone tools atómicas en simuladores versionados. | No duplica lógica de cálculo. |

## Las tres capas

1. **Capa de herramientas (`praxis-core` + servidor MCP).** Recibe argumentos tipados (Pydantic), ejecuta lógica determinista o consulta APIs y devuelve JSON limpio + metadatos (+ resumen compacto opcional para ahorrar tokens). Cero NLP, cero semantic-router, cero plantillas conversacionales.
2. **Capa de negocio y datos (`praxis-biz` + `praxis-knowledge`).** Aporta los datos del tenant, documentos y conocimiento. Es la única que conoce `company_id` de forma intensiva.
3. **Capa de canal (externa).** Un gateway opcional decide cómo invocar `praxis-core` (regex, semantic-router, formatters) para canales como WhatsApp/Telegram. No forma parte del core ni del paquete distribuido como motor.

## Estructura interna de `praxis-core`

```txt
praxis-core/
├── app/
│   ├── tools/                # Una carpeta por tool: finance/vat/, ...
│   │   └── <dominio>/<tool>/
│   │       ├── tool.py       # Decorador @tool + @tool_impl
│   │       ├── schemas.py    # Pydantic input/output
│   │       └── tests/
│   ├── providers/            # Clientes de APIs externas
│   ├── metadata/             # Modelo de metadatos y helpers
│   ├── auth.py               # API key, JWT, scopes y contexto HTTP
│   ├── tenancy.py            # Catálogos, activación y toolset por tenant
│   ├── registry.py           # Descubrimiento y registro de tools
│   ├── mcp_server.py         # Exposición MCP (SDK mcp)
│   ├── api/                  # Endpoints REST auxiliares (/health, admin)
│   └── main.py
└── tests/
```

Responsabilidades:

| Componente | Responsabilidad |
|---|---|
| `tools/` | Lógica determinista y esquemas. Fuente de verdad de cada herramienta. |
| `providers/` | Consultas a APIs externas con timeouts, reintentos, circuit breaker y caché. |
| `metadata/` | Construcción del bloque `metadata` común a toda respuesta. |
| `auth.py` | Autentica API key/JWT, construye `ToolContext` y aplica scopes/confirmación. |
| `tenancy.py` | Resuelve catálogo y activación por tenant; filtra tools anunciadas y ejecutables. |
| `registry.py` | Descubre tools y genera JSON Schema, catálogo MCP y documentación. |
| `mcp_server.py` | Expone las tools activas según `TenantProfile`. |
| `api/` | Solo operaciones auxiliares; la interfaz pública es MCP. |

## Flujo de ejecución

```txt
1. El arnés del LLM recibe la petición del usuario.
2. El LLM selecciona una tool MCP y envía argumentos tipados.
3. praxis-core valida la entrada (Pydantic).
4. Resuelve permisos y tenant (API key/JWT → `ToolContext`; nunca desde el cuerpo).
5. Comprueba caché (clave con source + parámetros + company_id si aplica).
6. Ejecuta:
   a. lógica determinista, o
   b. provider externo (con reintentos y fallback).
7. Construye el bloque de metadatos (fuente, vigencia, unidades...).
8. Registra la ejecución (ToolExecutionLog) con versión y fuente.
9. Devuelve { success, tool, data, metadata }.
```

Si el mismo core se usa desde un canal humano, el gateway externo formatea el JSON con Babel y plantillas deterministas; el core no cambia.

## Contrato de respuesta

Toda tool devuelve el mismo sobre:

```json
{
  "success": true,
  "tool": "finance.vat",
  "tool_version": "1.0.0",
  "data": {},
  "metadata": {
    "source": "deterministic",
    "source_type": "deterministic",
    "retrieved_at": "2026-11-12T12:00:00Z",
    "valid_until": null,
    "result_type": "calculation",
    "is_estimated": false,
    "confidence": null,
    "unit_system": "metric",
    "timezone": "Europe/Madrid",
    "warnings": [],
    "errors": []
  }
}
```

El detalle de campos, modos de respuesta y formateo está en [`08-formatting.md`](08-formatting.md). La especificación MCP está en [`09-mcp.md`](09-mcp.md).

## Aislamiento y multi-tenancy

- Toda tabla con datos de empresa lleva `company_id NOT NULL` y política RLS.
- El contexto de ejecución (`ToolContext`) transporta `user_id`, `company_id`, `role`, `channel` y `request_id`.
- La caché compartida (p. ej. precio del clima) no incluye `company_id`; la caché operacional sí.
- Ver [`05-data-models.md`](05-data-models.md) y [`07-security.md`](07-security.md).

## `praxis-sim`: simuladores complejos

Los simuladores (rentabilidad de placas solares, contratación de un comercial) **no** son tools atómicas del core. Son pipelines versionados que:

1. Declaran sus entradas y la lista de tools atómicas que orquestan.
2. Ejecutan cada paso y conservan los metadatos intermedios.
3. Devuelven un resultado compuesto con trazabilidad de cada cálculo y fuente.

De este modo el LLM solo redacta el informe final; nunca calcula. El detalle se documenta en la fase v2.

## Decisiones de arquitectura

Las decisiones relevantes están registradas en [`adr/`](adr/). Las iniciales: MCP como interfaz primaria (ADR-001), core stateless (ADR-002), RLS (ADR-003), código como fuente de verdad (ADR-004), almacenamiento en VPS (ADR-005), Decimal (ADR-006), `praxis-sim` (ADR-007) e ingesta manual (ADR-008).
