# PRAXIS

> Herramientas empresariales deterministas para agentes de IA, en formato API y MCP, independientes del agente que las consulte.

PRAXIS persigue dos objetivos:

- **Evitar alucinaciones:** los cálculos y las consultas se resuelven con lógica determinista o con fuentes externas verificables, no con el LLM.
- **Ahorrar tokens:** el agente no razona operaciones que se resuelven con una llamada tipada; recibe JSON limpio y metadatos.

Su valor no es la cantidad de herramientas, sino que cada resultado responda de forma fiable a:

> ¿Qué se calculó, con qué datos, con qué versión, con qué fuente, para qué empresa, bajo qué permisos y con qué vigencia?

## Estado

**Fase 1 — Implementación (en curso).** La documentación de la fase 0 está cerrada y el toolchain de desarrollo configurado; las tools se incorporan por tandas. El estado detallado, con tareas marcadas, está en [`TODO.md`](TODO.md). El alcance canónico sigue en [`docs/02-mvp-scope.md`](docs/02-mvp-scope.md).

## Arquitectura en una frase

`praxis-core` expone herramientas deterministas vía MCP; `praxis-knowledge` aporta conocimiento compartido y por empresa; `praxis-biz` gestiona datos y documentos del tenant; `praxis-sim` orquesta simuladores compuestos. El LLM lo pone el cliente.

## Monorepo

PRAXIS se distribuirá como monorepo con cuatro proyectos individuales. En esta fase 0 todavía no existen como directorios; se crean durante el MVP.

| Paquete | Responsabilidad |
|---|---|
| `praxis-core` | Motor de herramientas deterministas + servidor MCP (casi stateless). |
| `praxis-knowledge` | Base de conocimiento genérica y específica por empresa. |
| `praxis-biz` | Conectores, ingesta documental y caché operacional por empresa. |
| `praxis-sim` | Pipelines y simuladores compuestos versionados. |

La capa de canal (WhatsApp/Telegram, routing, formatters) es externa al core y no forma parte de `praxis-core`.

## Stack

- **Backend:** FastAPI, Pydantic v2, `uv`.
- **Base de datos:** PostgreSQL con `pgvector` (conocimiento) y PostGIS (geolocalización).
- **MCP:** `fastmcp` / `mcp`.
- **Licencia:** MIT.

## Quickstart

Requisitos: Python 3.12+ y [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn main:app --reload
```

Comprobar el estado del servidor:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Las herramientas del MVP y el servidor MCP se incorporarán durante la fase 1.

## Documentación

Índice en [`docs/`](docs/):

- [`00-overview.md`](docs/00-overview.md) — qué es PRAXIS, por qué y para quién.
- [`01-architecture.md`](docs/01-architecture.md) — verticales, capas y flujo de ejecución.
- [`02-mvp-scope.md`](docs/02-mvp-scope.md) — alcance, herramientas y criterios de corte.
- [`03-tools-catalog.md`](docs/03-tools-catalog.md) — catálogo de las 21 herramientas del MVP y backlog.
- [`04-routing.md`](docs/04-routing.md) — capa de canal y `intents.yaml` (v2).
- [`05-data-models.md`](docs/05-data-models.md) — dominios, RLS y modelos.
- [`06-external-apis.md`](docs/06-external-apis.md) — proveedores, límites y fallbacks.
- [`07-security.md`](docs/07-security.md) — multi-tenancy, GDPR y auditoría.
- [`08-formatting.md`](docs/08-formatting.md) — respuesta, canales y tonos.
- [`09-mcp.md`](docs/09-mcp.md) — especificación MCP.
- [`10-infrastructure.md`](docs/10-infrastructure.md) — stack, despliegue y observabilidad.
- [`11-success-metrics.md`](docs/11-success-metrics.md) — KPIs del proyecto.
- [`12-legal-notes.md`](docs/12-legal-notes.md) — notas legales españolas (borrador a validar).
- [`13-connectors.md`](docs/13-connectors.md) — conectores e integraciones.
- [`14-knowledge-governance.md`](docs/14-knowledge-governance.md) — curación, vigencia y citas.
- [`15-testing-and-evals.md`](docs/15-testing-and-evals.md) — tests, propiedades y evaluaciones.
- [`16-tool-authoring.md`](docs/16-tool-authoring.md) — guía para crear herramientas.
- [`17-versioning.md`](docs/17-versioning.md) — SemVer, deprecación y cambios incompatibles.
- [`adr/`](docs/adr/) — Architecture Decision Records.

## Contribuir

La guía para crear nuevas herramientas está en [`docs/16-tool-authoring.md`](docs/16-tool-authoring.md). Los criterios de entrada se resumen en [`docs/02-mvp-scope.md`](docs/02-mvp-scope.md#criterios-de-entrada-para-herramientas-de-backlog).

## Aviso legal

PRAXIS no presta asesoramiento jurídico, fiscal ni financiero. Las herramientas legales y laborales devuelven señales para revisar, no recomendaciones vinculantes. Cada instalación es responsable de usar sus propias claves de APIs externas y de cumplir sus términos de servicio y las obligaciones de protección de datos aplicables.
