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

- [ ] `app/data/holidays_es.json` versionado (nacionales + CCAA).
- [ ] Script generador `scripts/generate_holidays.py`.
- [ ] Fallback con warning `local_holidays_unavailable` si faltan datos locales.

### Tools semana 1 (11)

- [ ] `validate.spanish_id` — NIF/CIF/NIE.
- [ ] `validate.iban` — IBAN + BIC.
- [ ] `validate.email_phone` — email y teléfono.
- [ ] `units.convert` — conversión con `pint` (boundary `Decimal → float → Decimal`).
- [ ] `datetime.calc` — fechas, diferencias y semana ISO.
- [ ] `datetime.business_days` — días hábiles con festivos.
- [ ] `calendar.deadline_remaining` — cierre de mes/trimestre/año.
- [ ] `finance.vat` — sumar, extraer y restar IVA.
- [ ] `finance.margin` — margen y markup.
- [ ] `finance.discounts` — descuentos sucesivos y precio original.
- [ ] `finance.loan_schedule` — cuadro francés/italiano, cierre exacto a `0.00`.
- [ ] Golden tests (feliz, límite, error) por tool.
- [ ] Propiedades `Hypothesis` donde aplique (IVA, descuentos, préstamo, unidades, días hábiles).

### Servidor MCP

- [ ] Rutas `POST /api/tools/{name}` generadas desde el registry.
- [ ] Montaje de `fastapi-mcp` en `/mcp` (o SDK `mcp` si degrada esquemas).
- [ ] `app/main.py` con `/health`; retirar `main.py` raíz.
- [ ] Smoke test: invocar `finance.vat` vía MCP y validar el sobre completo.

### Documentación de la tanda

- [ ] README con arranque (`uv run uvicorn app.main:app`) y prueba MCP.
- [ ] Revisar que las specs implementadas no requieran correcciones.

## Fase 1 — Tanda 2: proveedores externos

- [ ] `currency.convert` — BCE, caché y `rate_date`.
- [ ] `weather.forecast` — Open-Meteo, granularidad diaria/horaria.
- [ ] `geo.geocode` — CartoCiudad.
- [ ] Tests con `respx`: éxito, timeout, 429, 5xx y fallback.
- [ ] Fichas de proveedor y `valid_until` en metadatos.

## Fase 1 — Tanda 3: negocio, seguridad y datos

### Tools restantes del MVP (7)

- [ ] `procurement.tpv_savings`.
- [ ] `procurement.compare_offers`.
- [ ] `calendar.list_events` (OAuth Google Calendar).
- [ ] `calendar.create_event` (confirmación humana).
- [ ] `documents.extract_invoice` (PDF → JSON).
- [ ] `documents.generate_invoice` (HTML → PDF).
- [ ] `alerts.contract_renewal` (60/30/15 días).

### Seguridad, tenants y efectos

- [ ] API key con Argon2id + JWT simple.
- [ ] `ToolContext` construido desde el token; nunca aceptar `company_id` del cliente.
- [ ] Toolsets por `TenantProfile` (intersección catálogo/permisos/activación).
- [ ] Idempotencia por (`tool`, `company_id`, `idempotency_key`).
- [ ] Confirmación humana en tools con `requires_confirmation`.
- [ ] RLS en PostgreSQL y seeders mínimos.
- [ ] `ToolExecutionLog` con empresa, usuario, versión y fuente.

## Cierre Fase 1

- [ ] CI: `ruff check`, `ruff format --check`, `pyright`, `pytest`.
- [ ] Cobertura ≥ 90 % en lógica determinista; ≥ 80 % global.
- [ ] Escenario Hotel: agenda + cita con confirmación.
- [ ] Escenario CEO/Polígono: IVA + factura PDF + comparación de ofertas.
- [ ] Escenario Asociación: ahorro TPV + alerta de renovación.
- [ ] Actualizar `README.md` (estado y quickstart definitivo).

## Huecos y decisiones pendientes

- [ ] Cerrar las decisiones pendientes de las specs en [`docs/tools/README.md`](docs/tools/README.md).
- [ ] Documentar/implementar el servicio de enlaces QR (`qr.generate`, v3) si se prioriza.
- [ ] Revisar `docs/12-legal-notes.md` con validación profesional.
