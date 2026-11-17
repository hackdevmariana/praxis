# TODO — PRAXIS

> Tablero vivo de ejecución. Marca `[x]` al completar y añade la fecha/commit cuando aporte trazabilidad.
> El alcance canónico vive en [`docs/02-mvp-scope.md`](docs/02-mvp-scope.md); este fichero solo ordena el trabajo.

## Fase 0 — Documentación

- [x] Documentos base `docs/00`–`17`.
- [x] ADRs `001`–`008`.
- [x] 42 specs de tools (21 MVP + 18 v2 + 3 backlog) enlazadas desde el índice.
- [x] Verificación global de enlaces Markdown.
- [ ] Validación legal de [`docs/12-legal-notes.md`](docs/12-legal-notes.md) (sigue en borrador).

## Fase 1 — Tanda 1: esqueleto + tools semana 1 + MCP

### Preparación

- [x] Toolchain de desarrollo: `pytest`, `pytest-cov`, `ruff`, `pyright`, `hypothesis`, `time-machine`.
- [x] Configuración de `ruff` (lint + formato, `docs/` excluido).
- [x] Configuración de `pyright` en modo estricto.
- [x] Configuración de `pytest` (marker `integration`) y cobertura.
- [x] Estructura inicial `app/` y `tests/`.
- [x] Dependencias de runtime: `python-stdnum`, `email-validator`, `phonenumbers`, `pint`.

### Núcleo `app/`

- [x] `money.py` — `Decimal`, `ROUND_HALF_UP`, serialización como string.
- [x] `clock.py` — reloj en `Europe/Madrid`, inyectable en tests.
- [x] `errors.py` — `ToolError` y códigos de error MCP.
- [x] `context.py` — `ToolContext` (usuario, empresa, rol, canal, `request_id`).
- [x] `envelope.py` — sobre de respuesta de [`docs/08-formatting.md`](docs/08-formatting.md).
- [x] `metadata.py` — `build_metadata()`.
- [x] `registry.py` — decorador `@tool`, `ToolSpec`, JSON Schema y descubrimiento.
- [x] Tests del núcleo (esquema, sobre, redondeos).

### Dataset de festivos

- [x] `app/data/holidays_es.json` versionado (nacionales + CCAA).
- [x] Script generador `scripts/generate_holidays.py`.
- [x] Fallback con warning `local_holidays_unavailable` si faltan datos locales.

### Tools semana 1 (11)

- [x] `validate.spanish_id` — NIF/CIF/NIE.
- [x] `validate.iban` — IBAN + BIC.
- [x] `validate.email_phone` — email y teléfono.
- [x] `units.convert` — conversión con `pint` (boundary `Decimal → float → Decimal`).
- [x] `datetime.calc` — fechas, diferencias y semana ISO.
- [x] `datetime.business_days` — días hábiles con festivos.
- [x] `calendar.deadline_remaining` — cierre de mes/trimestre/año.
- [x] `finance.vat` — sumar, extraer y restar IVA.
- [x] `finance.margin` — margen y markup.
- [x] `finance.discounts` — descuentos sucesivos y precio original.
- [x] `finance.loan_schedule` — cuadro francés/italiano, cierre exacto a `0.00`.
- [x] Golden tests (feliz, límite, error) por tool.
- [x] Propiedades `Hypothesis` donde aplique (IVA, descuentos, préstamo, unidades, días hábiles).

### Servidor MCP

- [x] Rutas `POST /api/tools/{name}` generadas desde el registry.
- [x] Montaje MCP en `/mcp` con el SDK oficial (fastapi-mcp 0.4 incompatible con mcp 2.x).
- [x] `app/main.py` con `/health`; retirar `main.py` raíz.
- [x] Smoke test: invocar `finance.vat` vía MCP y validar el sobre completo.

### Documentación de la tanda

- [x] README con arranque (`uv run uvicorn app.main:app`) y prueba MCP.
- [x] Revisar que las specs implementadas no requieran correcciones.

## Fase 1 — Tanda 2: proveedores externos

- [x] `currency.convert` — BCE, caché y `rate_date`.
- [x] `weather.forecast` — Open-Meteo, granularidad diaria/horaria.
- [x] `geo.geocode` — CartoCiudad.
- [x] Tests con `respx`: éxito, timeout, 429, 5xx y fallback.
- [x] Fichas de proveedor y `valid_until` en metadatos.

## Fase 1 — Tanda 3: negocio, seguridad y datos

### Tools restantes del MVP (7)

- [x] `procurement.tpv_savings`.
- [x] `procurement.compare_offers`.
- [ ] `calendar.list_events` (tool y conector inyectable listos; falta OAuth real).
- [ ] `calendar.create_event` (tool, confirmación e idempotencia listos; faltan OAuth real y persistencia).
- [ ] `documents.extract_invoice` (pdfplumber y caché listos; falta OCR/Tesseract).
- [ ] `documents.generate_invoice` (cálculo, numeración, idempotencia y adaptadores listos; falta WeasyPrint/almacenamiento real).
- [ ] `alerts.contract_renewal` (tool, avisos y tests listos; faltan repositorio persistente y envío real).

### Seguridad, tenants y efectos

- [x] API key con Argon2id + JWT simple.
- [x] `ToolContext` construido desde el token; nunca aceptar `company_id` del cliente.
- [x] Toolsets por `TenantProfile` (catálogo/activación inyectables y persistentes con RLS).
- [x] Idempotencia central por (`tool`, `company_id`, `idempotency_key`) con `input_hash` (stores in-memory y SQLAlchemy con RLS).
- [x] Confirmación humana en tools con `requires_confirmation` (cabecera `X-PRAXIS-Confirm`; UI real pendiente).
- [x] Esquema mínimo y RLS en PostgreSQL con tests de aislamiento y seeder idempotente de demo.
- [x] `ToolExecutionLog` con empresa, usuario, versión, fuente, `input_hash` y duración.

## Cierre Fase 1

- [x] CI: `ruff check`, `ruff format --check`, `pyright`, `pytest`.
- [x] Cobertura ≥ 90 % en lógica determinista; ≥ 80 % global.
- [x] Escenario Hotel: agenda + cita con confirmación.
- [x] Escenario CEO/Polígono: IVA + extracción de factura PDF + comparación de ofertas.
- [x] Escenario Asociación: ahorro TPV + alerta de renovación.
- [x] Actualizar `README.md` (estado y quickstart definitivo).

### Cierre Fase 2

- [x] Stores SQLAlchemy de idempotencia y toolsets protegidos por RLS.
- [x] Engine y wiring condicional desde `DATABASE_URL`.
- [x] Seeder idempotente de tenants demo y fuentes de datos globales.
- [x] Tests de integración RLS para stores persistentes.

## Huecos y decisiones pendientes

- [ ] Cerrar las decisiones pendientes (§8) de cada ficha en [`docs/tools/`](docs/tools/README.md).
- [ ] Documentar/implementar el servicio de enlaces QR (`qr.generate`, v3) si se prioriza.
- [ ] Revisar `docs/12-legal-notes.md` con validación profesional.
