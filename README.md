# PRAXIS

> Herramientas empresariales deterministas para agentes de IA, en formato API y MCP, independientes del agente que las consulte.

PRAXIS persigue dos objetivos:

- **Evitar alucinaciones:** los cálculos y las consultas se resuelven con lógica determinista o con fuentes externas verificables, no con el LLM.
- **Ahorrar tokens:** el agente no razona operaciones que se resuelven con una llamada tipada; recibe JSON limpio y metadatos.

Su valor no es la cantidad de herramientas, sino que cada resultado responda de forma fiable a:

> ¿Qué se calculó, con qué datos, con qué versión, con qué fuente, para qué empresa, bajo qué permisos y con qué vigencia?

## Estado

**Fase 2 — v2 (en curso).** Las 21 tools del MVP y 4 tools v2 de finanzas determinista (`finance.business_kpi`, `finance.ebitda`, `finance.break_even` y `finance.cashflow_13w`) están registradas y expuestas por REST y MCP; el toolchain, la autenticación, el control de toolsets por tenant, la idempotencia y el registro de ejecución funcionan con stores en memoria o SQLAlchemy protegidos por RLS. El esquema, el seeder demo y los defaults §8 del MVP están cerrados. Siguen pendientes la validación legal, el QR v3, el resto del roadmap v2 y los adaptadores reales de Google Calendar, OCR, renderizado PDF, almacenamiento de documentos, repositorio de contratos y envío de avisos; el estado detallado está en [`TODO.md`](TODO.md) y el alcance canónico en [`docs/02-mvp-scope.md`](docs/02-mvp-scope.md).

## Arquitectura en una frase

`praxis-core` expone herramientas deterministas vía MCP; `praxis-knowledge` aporta conocimiento compartido y por empresa; `praxis-biz` gestiona datos y documentos del tenant; `praxis-sim` orquesta simuladores compuestos. El LLM lo pone el cliente.

## Monorepo

PRAXIS se distribuirá como monorepo con cuatro proyectos individuales. Durante el MVP el código compartido vive en `app/`; los directorios de los paquetes se crearán cuando se separen responsabilidades.

| Paquete | Responsabilidad |
|---|---|
| `praxis-core` | Motor de herramientas deterministas + servidor MCP (casi stateless). |
| `praxis-knowledge` | Base de conocimiento genérica y específica por empresa. |
| `praxis-biz` | Conectores, ingesta documental y caché operacional por empresa. |
| `praxis-sim` | Pipelines y simuladores compuestos versionados. |

La capa de canal (WhatsApp/Telegram, routing, formatters) es externa al core y no forma parte de `praxis-core`.

## Stack

- **Backend:** FastAPI, Pydantic v2, `uv`.
- **Base de datos:** PostgreSQL con RLS por empresa; `pgvector` y PostGIS quedan previstos para capas posteriores.
- **MCP:** `MCPServer` (antes FastMCP) del SDK oficial `mcp` 2.x (streamable HTTP).
- **Licencia:** [MIT](LICENSE). Historial de cambios en [`CHANGELOG.md`](CHANGELOG.md).

## Quickstart

Requisitos: Python 3.12+ y [`uv`](https://docs.astral.sh/uv/). Las migraciones y los tests de integración RLS usan PostgreSQL/testcontainers; los tests de integración se omiten localmente si Docker no está disponible y se ejecutan en CI.

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Comprobar el estado del servidor:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","service":"praxis","version":"0.1.0","tools":25}
```

El catálogo incluye 25 tools (21 del MVP y 4 v2) y se puede invocar por REST:

```bash
curl -X POST http://127.0.0.1:8000/api/tools/finance.vat \
  -H "Content-Type: application/json" \
  -d '{"amount":"1000.00"}'
```

El servidor MCP (streamable HTTP) escucha en `http://127.0.0.1:8000/mcp`.

### Base de datos

El servidor arranca sin base de datos y usa stores en memoria. Con `DATABASE_URL`, la app usa stores SQLAlchemy para idempotencia, toolsets y auditoría. Para crear el esquema RLS y cargar los tenants demo:

```bash
export DATABASE_URL='postgresql+asyncpg://praxis:praxis@localhost:5432/praxis'
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

El seeder es idempotente y crea los perfiles `hotel`, `poligono` y `asociacion` con UUID fijos, además de las fuentes de datos globales.

### Autenticación

En local, `PRAXIS_AUTH_REQUIRED=false` permite probar sin credenciales. En producción, activa autenticación con `PRAXIS_AUTH_REQUIRED=true` y `PRAXIS_JWT_SECRET` (o configura `PRAXIS_API_KEYS_FILE`). Un token de desarrollo se emite con:

```bash
export PRAXIS_AUTH_REQUIRED=true
export PRAXIS_JWT_SECRET='secret-de-al-menos-32-caracteres'
uv run python scripts/issue_token.py \
  --subject demo \
  --company-id 11111111-1111-4111-8111-111111111111 \
  --role admin \
  --scope finance.calculate
```

Las tools con efectos exigen `X-PRAXIS-Confirm: true`. Ver [`07-security.md`](docs/07-security.md).

### Tests y calidad

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --cov=app --cov-report=term-missing
uv run pytest -q -m integration  # se omite si no hay Docker; se ejecuta en CI
```

CI ejecuta lint, formato, tipos, tests y umbrales de cobertura: ≥ 80 % global y ≥ 90 % en lógica determinista.

### Adaptadores reales

`calendar.*`, `documents.*` y `alerts.contract_renewal` siguen fallando cerrado si no se activan: devuelven `connector_not_connected`, `provider_unavailable` o `contract_not_found`. Los adaptadores reales se instalan en `create_app` desde `app/providers/adapters.py`:

```bash
export PRAXIS_CALENDAR_ADAPTER=google GOOGLE_REFRESH_TOKEN=...  # OAuth + espejo SQL
export PRAXIS_EVENT_REPOSITORY=sql PRAXIS_CONTRACT_REPOSITORY=sql PRAXIS_ALERT_REPOSITORY=sql
export PRAXIS_DOCUMENTS_ADAPTER=local PRAXIS_PDF_RENDERER=weasyprint
export PRAXIS_OCR_ADAPTER=tesseract PRAXIS_ALERT_NOTIFIER=smtp SMTP_HOST=...
```

Las credenciales, binarios del sistema (`tesseract`, librerías nativas de WeasyPrint) y el directorio de documentos deben provisionarse por entorno; el inventario completo está en [`.env.example`](.env.example) y [`docs/10-infrastructure.md`](docs/10-infrastructure.md). Sin flags, los tests de escenarios instalan adaptadores falsos.

## Documentación

Índice maestro en [`docs/README.md`](docs/README.md). Índices específicos: [especificaciones de tools](docs/tools/README.md), [ADRs](docs/adr/README.md) y [scripts](scripts/README.md).

- [`00-overview.md`](docs/00-overview.md) — qué es PRAXIS, por qué y para quién.
- [`01-architecture.md`](docs/01-architecture.md) — verticales, capas y flujo de ejecución.
- [`02-mvp-scope.md`](docs/02-mvp-scope.md) — alcance, herramientas y criterios de corte.
- [`03-tools-catalog.md`](docs/03-tools-catalog.md) — catálogo de las 25 herramientas implementadas y backlog.
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
