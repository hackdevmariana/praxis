---
estado: MVP
version: 0.1.0
---

# Infraestructura

## Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12+ |
| Backend | FastAPI, Pydantic v2 |
| MCP | SDK oficial `mcp` |
| Persistencia | PostgreSQL, SQLAlchemy 2, Alembic; `pgvector`/PostGIS *(objetivo de capas posteriores)* |
| Caché | *(Objetivo)* Redis (`cashews`); sin dependencia/uso en el MVP actual |
| Clientes HTTP | `httpx`; reintentos estandarizados con `stamina` *(objetivo)* |
| Tareas | *(Objetivo)* `arq`/Redis; hoy no hay worker (seeders por CLI, p. ej. `scripts/seed_demo.py`) |
| Servidor ASGI | `uvicorn[standard]`; `granian` *(objetivo producción)* |
| Config | Variables de entorno / `.env` leídas en código; `pydantic-settings` *(objetivo)* |
| Calidad | `uv`, `ruff`, `pyright`, `pytest` |
| Contenedores | Docker Compose (VPS) |

## Entornos

| Entorno | Uso | Datos |
|---|---|---|
| `local` | Desarrollo | Sin BD por defecto; PostgreSQL/testcontainers para integración, datos demo opcionales |
| `staging` | Validación | Datos sintéticos |
| `production` | Clientes | VPS por instalación, datos reales |

Cada instalación es independiente (self-hosted): sus claves, su base de datos, sus datos.

## Servicios (objetivo Docker Compose)

```txt
services:
  api        # FastAPI + MCP (ASGI; uvicorn hoy, granian objetivo)
  worker     # (objetivo) arq: seeders, alertas, sincronizaciones
  db         # PostgreSQL (+ extensiones según despliegue)
  redis      # (objetivo) caché y colas
  reverse    # (objetivo) Caddy/Traefik: TLS y proxy
```

> No hay `Dockerfile` ni `docker-compose*.yml` versionados en el estado actual; el arranque local funciona sin base de datos.

- **Volúmenes:** `db-data`, `redis-data`, `documents` (almacenamiento local de documentos, ADR-005).
- **Red:** solo el proxy expone puertos; `db`/`redis` en red interna.
- **TLS:** obligatorio; certificados gestionados por el proxy.

## Configuración (`.env`)

Variables principales (nunca en git). En el MVP read-from-env cubre autenticación y `DATABASE_URL`; el resto son configuración objetivo o de instalaciones futuras (algunas URLs de proveedor están hoy fijas en código):

```txt
PRAXIS_ENV=production
PRAXIS_SECRET_KEY=...
DATABASE_URL=postgresql+asyncpg://...
PRAXIS_DB_APP_PASSWORD=...   # rol no superusuario usado por la API
REDIS_URL=redis://...
# Autenticación (MVP)
PRAXIS_AUTH_REQUIRED=true
PRAXIS_JWT_SECRET=...
PRAXIS_JWT_ALGORITHM=HS256
PRAXIS_JWT_ISSUER=praxis
PRAXIS_JWT_AUDIENCE=praxis-mcp
PRAXIS_JWT_EXPIRES_MINUTES=30
PRAXIS_API_KEYS_FILE=/etc/praxis/api_keys.json

# APIs externas (por instalación)
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1
CARTOCIUDAD_BASE_URL=https://www.cartociudad.es/geocoder/api

# Google Calendar (OAuth por usuario)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=...

# Cifrado de campos sensibles
FIELD_ENCRYPTION_KEYS=...   # versionadas
```

`AuthSettings.from_env` valida la configuración de autenticación cuando se construye y falla rápido si `PRAXIS_AUTH_REQUIRED=true` y falta el secreto JWT o es inválido.

## Base de datos

- **Extensiones:** `vector` (pgvector), `postgis`, `pgcrypto` (si aplica).
- **Migraciones:** Alembic (`migrations/`). La migración inicial crea el esquema tenant, las políticas RLS y el rol `praxis_app`; se aplica con `uv run alembic upgrade head` y `DATABASE_URL`.
- **RLS:** `app/db/rls.py` inyecta `praxis.company_id` por transacción. El código de aplicación debe usar `company_session(engine, company_id)` para cualquier consulta tenant.
- La migración `0002_tool_execution_log` añade la tabla de auditoría de ejecuciones con la misma política RLS.
- `create_app` usa stores SQLAlchemy cuando hay `DATABASE_URL`; sin ella mantiene los stores en memoria para desarrollo y tests.
- **Seeders:** CLI independiente (no dentro de FastAPI), ejecutable por cron.
  - `uv run python scripts/seed_demo.py` crea/actualiza los tres tenants demo y las fuentes globales con UUID fijos.
  - Idempotentes, versionados y auditables (`created_by: seeder`, `source`).
  - Datasets pendientes: festivos, tipos de IVA, plazos fiscales, municipios (8.131) y CNAE.
- **Backups:** `pg_dump` diario + retención; probar restauración mensualmente.

## Observabilidad (estado actual / objetivo)

| Aspecto | Estado actual | Objetivo |
|---|---|---|
| Logs | Logging estándar en puntos concretos | `structlog` JSON a stdout |
| Correlación | `request_id` en contexto/headers cuando aplica | `asgi-correlation-id` end-to-end |
| Errores | No integrado | `sentry-sdk` opcional |
| Métricas | No integrado | `prometheus-client` |
| Tracing | No integrado | OpenTelemetry (v2) |

Métricas mínimas:

- Latencia p50/p95 por tool.
- Tasa de error y de fallback por proveedor.
- Ratio de cache hit.
- Llamadas por tenant/herramienta (cuotas).
- Tools con `partial_result` o `warnings`.

## CI/CD

Pipeline mínimo:

1. `uv sync --frozen`.
2. `uv run ruff check .` + `uv run ruff format --check .`.
3. `uv run pyright` (type checking estricto).
4. `uv run python scripts/check_markdown.py` (enlaces, anclas y frontmatter).
5. `uv run pytest -q --cov=app --cov-report=xml --cov-fail-under=80` y cobertura ≥ 90 % en lógica determinista.
6. Tests de integración con `testcontainers[postgres]` (RLS): `uv run pytest -m integration`.
7. Pendiente de automatizar: `pip-audit`, build de imagen, despliegue a staging y migraciones Alembic antes de arrancar la nueva versión.

Despliegue:

- Imágenes versionadas; sin cambios destructivos sin migración previa.
- Healthcheck `/health` implementado (estado/versión/nº de tools). Readiness con validación de DB/Redis pendiente.
- Rolling restart con el proxy manteniendo conexiones.

## Rendimiento y límites

- `httpx` disponible para clientes externos; timeouts, reintentos (`stamina`) y límites por proveedor: *(objetivo, pendiente de estandarizar)*.
- `orjson` como `default_response_class`: *(objetivo)*, no configurado en `create_app`.
- `polars` para CSV/Excel: *(objetivo)*, no es dependencia actual.
- Rate limiting (`slowapi`/`fastapi-limiter`) por usuario/empresa/tool: *(objetivo)*, no implementado.
- Presupuesto de llamadas externas por ventana para evitar bucles de agentes: *(objetivo)*.

## Escalado (futuro)

- La API es casi stateless: escalado horizontal detrás del proxy.
- Redis compartido para caché/colas; PostgreSQL con réplicas de lectura si hace falta.
- Documentos a S3/MinIO en v2; URLs firmadas.
- Multi-instancia por tenant aislada por `company_id` y RLS.

## Riesgos operativos

| Riesgo | Mitigación |
|---|---|
| Caída de API externa | Fallback + circuit breaker + caché por vigencia |
| Fuga entre tenants | RLS + tests de aislamiento en CI |
| Crecimiento de documentos | Límites de tamaño + S3 en v2 |
| Secretos filtrados | `.env` fuera de git + rotación |
| Migraciones fallidas | Backups + migraciones reversibles |
