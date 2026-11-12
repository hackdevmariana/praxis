# PRAXIS

> Herramientas empresariales deterministas para agentes de IA, en formato API y MCP, independientes del agente que las consulte.

PRAXIS persigue dos objetivos:

- **Evitar alucinaciones:** los cálculos y las consultas se resuelven con lógica determinista o con fuentes externas verificables, no con el LLM.
- **Ahorrar tokens:** el agente no razona operaciones que se resuelven con una llamada tipada; recibe JSON limpio y metadatos.

Su valor no es la cantidad de herramientas, sino que cada resultado responda de forma fiable a:

> ¿Qué se calculó, con qué datos, con qué versión, con qué fuente, para qué empresa, bajo qué permisos y con qué vigencia?

## Estado

**Fase 0 — Documentación.** El repositorio contiene el marco del proyecto y un servidor FastAPI mínimo (`/health`) como punto de partida. Aún no hay herramientas implementadas. El alcance está en [`docs/02-mvp-scope.md`](docs/02-mvp-scope.md).

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
- [`02-mvp-scope.md`](docs/02-mvp-scope.md) — alcance, herramientas y criterios de corte.

El resto de documentos (arquitectura, catálogo, modelos de datos, seguridad, MCP, etc.) se añaden en las siguientes iteraciones de la fase 0.

## Contribuir

La guía para contribuidores y para crear nuevas herramientas estará en `docs/16-tool-authoring.md` (fase 0). Criterios de entrada resumidos en [`docs/02-mvp-scope.md`](docs/02-mvp-scope.md#criterios-de-entrada-para-herramientas-de-backlog).

## Aviso legal

PRAXIS no presta asesoramiento jurídico, fiscal ni financiero. Las herramientas legales y laborales devuelven señales para revisar, no recomendaciones vinculantes. Cada instalación es responsable de usar sus propias claves de APIs externas y de cumplir sus términos de servicio y las obligaciones de protección de datos aplicables.
