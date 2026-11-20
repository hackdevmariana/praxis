# TODO — PRAXIS

> Tablero vivo de ejecución. Marca `[x]` al completar y añade la fecha/commit cuando aporte trazabilidad.
> El alcance canónico vive en [`docs/02-mvp-scope.md`](docs/02-mvp-scope.md); este fichero solo ordena el trabajo.

## Fase 0 — Documentación

- [x] Documentos base `docs/00`–`17`.
- [x] ADRs `001`–`008`.
- [x] 42 specs de tools (21 MVP + 18 v2 + 3 backlog) enlazadas desde el índice.
- [x] Verificación global de enlaces Markdown.
- [x] Índices `docs/README.md`, `docs/adr/README.md` y `scripts/README.md`.
- [x] Checker automático de Markdown en CI (`scripts/check_markdown.py`).
- [x] Revisión de docs núcleo, ADRs y specs frente al código actual.
- [x] Artefactos `LICENSE`, `CHANGELOG.md`, `.env.example` e índice de fixtures.
- [ ] Validación legal de [`docs/12-legal-notes.md`](docs/12-legal-notes.md) (sigue en borrador).

> Fuera del MVP por decisión documentada: `intents.yaml` (v2), `Dockerfile`/`docker-compose.yml` (objetivo de despliegue) y los paquetes separados `praxis-biz`/`praxis-knowledge`/`praxis-sim`.

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
- [x] Montaje MCP en `/mcp` con `MCPServer` (FastMCP) del SDK `mcp` 2.x (fastapi-mcp 0.4 descartado por incompatibilidad).
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
- [x] `calendar.list_events` — conector Google Calendar con OAuth refresh (`PRAXIS_CALENDAR_ADAPTER=google`).
- [x] `calendar.create_event` — OAuth, confirmación, idempotencia y espejo persistente (`PRAXIS_EVENT_REPOSITORY=sql`).
- [x] `documents.extract_invoice` — pdfplumber, caché y OCR Tesseract opcional (`PRAXIS_OCR_ADAPTER=tesseract`).
- [x] `documents.generate_invoice` — WeasyPrint y almacén local con numeración persistente (`PRAXIS_DOCUMENTS_ADAPTER=local`).
- [x] `alerts.contract_renewal` — repositorio SQL y notificador SMTP (`PRAXIS_ALERT_NOTIFIER=smtp`).

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

### Cierre Fase 3

- [x] Decisiones cerradas con defaults en las 42 specs (§8, o §5/§6 en backlog) y convención documentada en `docs/tools/README.md`.
- [x] Contradicciones resueltas en `compare_offers`, `datetime.calc`, `validate.spanish_id` y `generate_invoice`.

## Fase 2 — v2 (en curso)

### Finanzas determinista

- [x] `finance.business_kpi` — KPIs con datos aportados y ratios sin denominador definido.
- [x] `finance.ebitda` — EBITDA, EBITDA ajustado y EBIT.
- [x] `finance.break_even` — equilibrio unitario, objetivo y margen de seguridad.
- [x] `finance.cashflow_13w` — previsión semanal a 13 semanas.
- [x] Tests golden, límites, errores, propiedades y smoke REST para las 4 tools.
- [x] Specs §8 y catálogo actualizados con las decisiones implementadas.

### Compras v2

- [x] `procurement.detect_price_increase` — umbrales fijos, basis points y propiedades.
- [x] `procurement.savings_ledger` — `savings_entries` con RLS y proveedor SQL inyectable.
- [x] `procurement.renewal_calendar` — renovaciones desde contratos, reglas y avisos.
- [x] `procurement.rfp_generation` — pliego Markdown/PDF con confirmación e idempotencia central.
- [x] Tests golden, límites, errores, propiedades, integración RLS y smoke REST para las 4 tools.
- [x] Specs §8, catálogo y modelos de datos actualizados con las decisiones implementadas.

### Energía v2

- [x] `energy.carbon_footprint` — factores versionados, personalizables y análisis por alcance/fuente.
- [x] `energy.tariff_simulator` — reparto punta/valle, costes anuales y ranking de 2-5 tarifas.
- [x] `energy.self_consumption_payback` — flujo anual, payback simple/interpolado, VAN y TIR por bisección.
- [x] Tests golden, límites, errores, propiedades y smoke REST para las 3 tools.
- [x] Specs §8 y catálogo actualizados con las decisiones implementadas.

### Pendiente del roadmap v2

- [ ] Conectores contables y bancarios (PSD2) para KPIs sobre datos reales del tenant.
- [ ] ESIOS/OMIE y cadena de herramientas de energía.
- [ ] Routing semántico y gateway WhatsApp/Telegram.
- [ ] S3/MinIO, OIDC y simuladores `praxis-sim`.

## Huecos y decisiones pendientes

- [x] Cerrar las decisiones §8 con defaults acordados en [`docs/tools/`](docs/tools/README.md); los restantes requieren producto, proveedor o validación legal.
- [ ] Documentar/implementar el servicio de enlaces QR (`qr.generate`, v3) si se prioriza.
- [ ] Revisar `docs/12-legal-notes.md` con validación profesional.
- [ ] Provisión por entorno de secretos y binarios de sistema (OAuth/Google, Tesseract, WeasyPrint y SMTP).
