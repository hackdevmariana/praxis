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
| Persistencia | PostgreSQL + `pgvector` + PostGIS, SQLAlchemy 2, Alembic |
| Caché | Redis (`cashews`) |
| Clientes HTTP | `httpx` + `stamina` (reintentos) |
| Tareas | `arq` (Redis) para seeders/alertas; sin Celery en MVP |
| Servidor ASGI | `granian` (producción), `uvicorn[standard]` (desarrollo) |
| Config | `pydantic-settings`, `.env` |
| Calidad | `uv`, `ruff`, `pyright`, `pytest` |
| Contenedores | Docker Compose (VPS) |

## Entornos

| Entorno | Uso | Datos |
|---|---|---|
| `local` | Desarrollo | PostgreSQL/Redis en Docker, datos demo |
| `staging` | Validación | Datos sintéticos |
| `production` | Clientes | VPS por instalación, datos reales |

Cada instalación es independiente (self-hosted): sus claves, su base de datos, sus datos.

## Servicios (Docker Compose MVP)

```txt
services:
  api        # FastAPI + MCP (granian)
  worker     # arq: seeders, alertas, sincronizaciones
  db         # PostgreSQL + pgvector + PostGIS
  redis      # caché y colas
  reverse    # Caddy/Traefik: TLS y proxy
```

- **Volúmenes:** `db-data`, `redis-data`, `documents` (almacenamiento local de documentos, ADR-005).
- **Red:** solo el proxy expone puertos; `db`/`redis` en red interna.
- **TLS:** obligatorio; certificados gestionados por el proxy.

## Configuración (`.env`)

Variables principales (nunca en git):

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

`AuthSettings.from_env` valida el entorno al arrancar y falla rápido si falta el secreto JWT o la configuración es inválida.

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

## Observabilidad (MVP)

| Aspecto | Herramienta | Nota |
|---|---|---|
| Logs | `structlog` (JSON) | A stdout; rotación por el runtime |
| Correlación | `asgi-correlation-id` | `request_id` end-to-end |
| Errores | `sentry-sdk` | Opcional, activable por `.env` |
| Métricas | `prometheus-client` | Latencia, errores, cache hit, llamadas externas |
| Tracing | OpenTelemetry | v2; MVP con logs correlacionados |

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
4. `uv run pytest -q --cov=app --cov-report=xml --cov-fail-under=80` y cobertura ≥ 90 % en lógica determinista.
5. Tests de integración con `testcontainers[postgres]` (RLS): `uv run pytest -m integration`.
6. Pendiente de automatizar: `pip-audit`, build de imagen, despliegue a staging y migraciones Alembic antes de arrancar la nueva versión.

Despliegue:

- Imágenes versionadas; sin cambios destructivos sin migración previa.
- Healthcheck `/health` y readiness que valide DB/Redis.
- Rolling restart con el proxy manteniendo conexiones.

## Rendimiento y límites

- `orjson` como `default_response_class`.
- `httpx` con timeouts, reintentos (`stamina`) y límites de concurrencia por proveedor.
- `polars` para procesamiento de CSV/Excel en lugar de Pandas.
- Rate limiting (`slowapi`) por usuario/empresa/tool.
- Presupuesto de llamadas externas por ventana para evitar bucles de agentes.

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
