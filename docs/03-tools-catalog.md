---
estado: MVP
version: 0.1.0
---

# Catálogo de herramientas

Este documento describe las **21 herramientas del MVP** y el backlog documentado para la comunidad. La definición canónica vive en código (decorador `@tool`); este catálogo es su reflejo navegable.

## Convenciones

- **Nombre:** `<dominio>.<accion>` en inglés (`finance.vat`).
- **Versión:** SemVer por herramienta (ver [`17-versioning.md`](17-versioning.md)).
- **Sobre de respuesta:** `{ success, tool, tool_version, data, metadata }` (ver [`01-architecture.md`](01-architecture.md)).
- **Clasificación de datos:** `public | business | personal | sensitive`.
- **Flags:** `read_only`, `idempotent`, `requires_confirmation`.
- **Importes:** `Decimal` serializado como string; nunca `float`.
- **Permisos:** scopes del tipo `dominio.accion`.

## Resumen del MVP

Cada nombre enlaza a su spec detallada en [`docs/tools/`](tools/README.md).

| Dominio | Tools |
|---|---|
| Fechas | [`datetime.calc`](tools/datetime/calc.md), [`datetime.business_days`](tools/datetime/business_days.md), [`calendar.deadline_remaining`](tools/calendar/deadline_remaining.md) |
| Finanzas | [`finance.vat`](tools/finance/vat.md), [`finance.margin`](tools/finance/margin.md), [`finance.loan_schedule`](tools/finance/loan_schedule.md), [`finance.discounts`](tools/finance/discounts.md) |
| Validación | [`validate.spanish_id`](tools/validate/spanish_id.md), [`validate.iban`](tools/validate/iban.md), [`validate.email_phone`](tools/validate/email_phone.md), [`units.convert`](tools/units/convert.md) |
| Datos externos | [`currency.convert`](tools/currency/convert.md), [`weather.forecast`](tools/weather/forecast.md), [`geo.geocode`](tools/geo/geocode.md) |
| Compras | [`procurement.tpv_savings`](tools/procurement/tpv_savings.md), [`procurement.compare_offers`](tools/procurement/compare_offers.md) |
| Agenda | [`calendar.list_events`](tools/calendar/list_events.md), [`calendar.create_event`](tools/calendar/create_event.md) |
| Documentos | [`documents.extract_invoice`](tools/documents/extract_invoice.md), [`documents.generate_invoice`](tools/documents/generate_invoice.md) |
| Alertas | [`alerts.contract_renewal`](tools/alerts/contract_renewal.md) |

---

## Fechas

### `datetime.calc` — v1.0.0

Cálculos de fecha deterministas: hoy, sumar/restar días, diferencias, día de la semana, semana ISO, trimestre y semestre.

- `read_only: true`, `idempotent: true`, `requires_confirmation: false`
- Permiso: `datetime.read` · Clasificación: `public`
- Proveedor: determinista · Caché: n/a

| Entrada | Tipo | Notas |
|---|---|---|
| `operation` | enum | `today`, `add_days`, `diff_days`, `weekday`, `week_info` |
| `date` | date | Opcional según operación |
| `date_b` | date | Para `diff_days` |
| `days` | int | Para `add_days` |
| `timezone` | str | Por defecto `Europe/Madrid` |

Salida: `{ operation, date, days_diff, weekday, weekday_name, iso_week, iso_year, quarter, semester, day_of_year }` según operación.

### `datetime.business_days` — v1.0.0

Días hábiles entre dos fechas excluyendo festivos nacionales, autonómicos y locales.

- `read_only: true`, `idempotent: true`
- Permiso: `datetime.read` · Clasificación: `public`
- Proveedor: dataset de festivos (seeder) · Caché: n/a

| Entrada | Tipo | Notas |
|---|---|---|
| `start` | date | Inclusivo |
| `end` | date | Exclusivo salvo `include_end=true` |
| `municipality_code` | str | Código INE, opcional para festivos locales |
| `community` | str | CCAA, opcional |
| `include_end` | bool | Por defecto `false` |

Salida: `{ business_days, calendar_days, holidays_applied: [...] }`. Los avisos de cobertura (p. ej. `local_holidays_unavailable`) van en `metadata.warnings`.

### `calendar.deadline_remaining` — v1.0.0

Días restantes para cierre de mes, trimestre o año.

- `read_only: true`, `idempotent: true`
- Permiso: `datetime.read` · Clasificación: `public`
- Proveedor: determinista

| Entrada | Tipo |
|---|---|
| `period` | enum: `month`, `quarter`, `year` |
| `reference_date` | date (opcional) |
| `community` | str (opcional) |
| `municipality_code` | str (opcional) |
| `timezone` | str (por defecto `Europe/Madrid`) |

Salida: `{ period, period_start, deadline, days_remaining, business_days_remaining, holidays_applied }`.

---

## Finanzas

### `finance.vat` — v1.0.0

Sumar, extraer o restar IVA de un importe.

- `read_only: true`, `idempotent: true`
- Permiso: `finance.calculate` · Clasificación: `business`
- Proveedor: determinista

| Entrada | Tipo | Notas |
|---|---|---|
| `amount` | Decimal (string) | |
| `rate` | Decimal | Por defecto 21 |
| `operation` | enum | `add`, `extract`, `remove` |

Salida: `{ base_amount, vat_rate, vat_amount, total_amount, currency }`. Redondeo `ROUND_HALF_UP` a 2 decimales.

### `finance.margin` — v1.0.0

Margen comercial y markup.

- `read_only: true`, `idempotent: true`
- Permiso: `finance.calculate` · Clasificación: `business`

| Entrada | Tipo | Notas |
|---|---|---|
| `cost` | Decimal | Opcional si se da `price` |
| `price` | Decimal | Opcional si se da `cost` |
| `margin_pct` | Decimal | Opcional para calcular precio |

Salida: `{ cost, price, margin_amount, margin_pct, markup_pct, currency }`; `margin_pct`/`markup_pct` pueden ser `null` con warning.

### `finance.loan_schedule` — v1.0.0

Cuota y cuadro de amortización.

- `read_only: true`, `idempotent: true`
- Permiso: `finance.calculate` · Clasificación: `business`

| Entrada | Tipo |
|---|---|
| `principal` | Decimal |
| `annual_rate` | Decimal (por defecto 0) |
| `term_months` | int |
| `type` | enum: `french`, `italian` |

Salida: `{ principal, annual_rate, term_months, type, monthly_payment, first_payment, last_payment, total_interest, total_paid, schedule: [{period, payment, interest, principal, balance}], currency }`. En `italian`, `monthly_payment` es `null`.

### `finance.discounts` — v1.0.0

Descuentos sucesivos y cálculo del precio original.

- `read_only: true`, `idempotent: true`
- Permiso: `finance.calculate` · Clasificación: `business`

| Entrada | Tipo |
|---|---|
| `amount` | Decimal |
| `discounts` | list[Decimal] (1–10 elementos) |
| `operation` | enum: `apply`, `reverse` |

Salida: `{ original_amount, final_amount, discount_amount, effective_discount_pct, currency }`.

---

## Validación

### `validate.spanish_id` — v1.0.0

Valida NIF, NIE y CIF con `python-stdnum`. Un checksum válido **no** prueba que la empresa exista o esté activa.

- `read_only: true`, `idempotent: true`
- Permiso: `validation.check` · Clasificación: `personal`

| Entrada | Tipo |
|---|---|
| `value` | str |
| `type` | enum: `auto`, `nif`, `nie`, `cif` |

Salida: `{ valid, id_type, normalized, checksum_ok, reason, warning }`.

### `validate.iban` — v1.0.0

Valida IBAN (y opcionalmente BIC) con `python-stdnum`. No verifica que la cuenta esté operativa.

- Permiso: `validation.check` · Clasificación: `personal`

Salida: `{ valid, normalized, country, bban, bic_valid, reason, warning }`.

### `validate.email_phone` — v1.0.0

Valida formato de email (`email-validator`) y teléfono (`phonenumbers`). No verifica buzón ni titularidad.

- Permiso: `validation.check` · Clasificación: `personal`

Salida: `{ email_valid, email_normalized, email_reason, phone_valid, phone_e164, phone_international, phone_type, phone_country, phone_reason }`.

### `units.convert` — v1.0.0

Conversión de unidades con `pint`.

- `read_only: true`, `idempotent: true`
- Permiso: `units.convert` · Clasificación: `public`

| Entrada | Tipo |
|---|---|
| `value` | Decimal |
| `from_unit` | str |
| `to_unit` | str |
| `precision` | int (0–12, por defecto 6) |

Salida: `{ value, from_unit, to_unit, dimension, factor }`.

---

## Datos externos

Todas las tools externas incluyen `metadata.source`, `retrieved_at`, `valid_until` y política de caché. Fichas de proveedor en [`06-external-apis.md`](06-external-apis.md).

### `currency.convert` — v1.0.0

Conversión de divisas con tipos de referencia del BCE.

- `read_only: true`, `idempotent: true`
- Permiso: `currency.read` · Clasificación: `public`
- Proveedor: BCE · Caché: 12 h

| Entrada | Tipo |
|---|---|
| `amount` | Decimal |
| `from_currency` | str (ISO 4217) |
| `to_currency` | str |
| `date` | date (opcional) |

Salida: `{ amount, converted_amount, rate, rate_date, from_currency, to_currency }`. BTC no está cubierto por el BCE: devuelve `unsupported_currency`.

### `weather.forecast` — v1.0.0

Previsión meteorológica con Open-Meteo (temperatura, sensación, lluvia, viento, humedad, radiación, nubosidad, UV).

- `read_only: true`, `idempotent: true`
- Permiso: `weather.read` · Clasificación: `public`
- Proveedor: Open-Meteo · Caché: 30 min

| Entrada | Tipo |
|---|---|
| `latitude` | float |
| `longitude` | float |
| `days` | int (1-7, por defecto 3) |
| `granularity` | enum: `daily`, `hourly` |
| `variables` | list[str] (opcional) |
| `timezone` | str (por defecto `Europe/Madrid`) |

Salida: `{ location: { latitude, longitude, elevation, timezone }, granularity, points: [{ time, values }] }`. Unidades en `metadata.units`.

### `geo.geocode` — v1.0.0

Geocoding y reverse geocoding con CartoCiudad (IGN) y fallback Nominatim.

- `read_only: true`, `idempotent: true`
- Permiso: `geo.read` · Clasificación: `public`
- Proveedor: CartoCiudad · Fallback: Nominatim · Caché: 7 días

| Entrada | Tipo |
|---|---|
| `address` | str (para forward) |
| `latitude` / `longitude` | float (para reverse) |
| `municipality_code` | str (opcional) |
| `limit` | int (1-5, por defecto 1) |

Salida: `{ mode, results: [{ latitude, longitude, normalized_address, ine_code, municipality, province, postal_code, confidence, source }] }`.

---

## Compras

### `procurement.tpv_savings` — v1.0.0

Calcula el ahorro anual al cambiar de comisión de TPV.

- `read_only: true`, `idempotent: true`
- Permiso: `procurement.calculate` · Clasificación: `business`
- Perfil: `asociacion`

| Entrada | Tipo |
|---|---|
| `annual_card_turnover` | Decimal |
| `current_rate_pct` | Decimal |
| `new_rate_pct` | Decimal |
| `average_ticket` | Decimal (opcional) |

Salida: `{ current_cost, new_cost, annual_savings, monthly_savings, savings_pct, savings_per_ticket, currency }`.

### `procurement.compare_offers` — v1.0.0

Normaliza 2-5 presupuestos (PDF o datos estructurados) en una tabla comparable por coste total.

- `read_only: true`, `idempotent: true`
- Permiso: `procurement.calculate` · Clasificación: `business`
- Perfil: `asociacion`
- Depende de `documents.extract_invoice` para PDFs.

| Entrada | Tipo |
|---|---|
| `offers` | list[OfferInput] |
| `years` | int (por defecto 5) |
| `normalize_by` | enum: `total_cost`, `monthly`, `annual` |

`OfferInput`: `{ supplier, monthly_price, permanence_months, cancellation_cost, year2_price, year3_price, upfront_cost, vat_included, vat_rate, currency }`.

Salida: `{ years, normalize_by, currency, ranking, normalized_table }`. La tabla incluye coste recurrente, costes puntuales, total, anual, mensual, ranking y ahorro frente a la oferta más cara.

---

## Agenda

OAuth de Google **por usuario**: cada persona conecta su cuenta. Los eventos de empresa y personales viven en calendarios separados. Ver [`13-connectors.md`](13-connectors.md).

### `calendar.list_events` — v1.0.0

Lista eventos de la agenda del usuario en un rango.

- `read_only: true`, `idempotent: true`
- Permiso: `calendar.read` · Clasificación: `personal`
- Proveedor: Google Calendar · Caché: 60 s

| Entrada | Tipo |
|---|---|
| `start` | datetime |
| `end` | datetime |
| `calendar_id` | str (opcional) |
| `max_results` | int (1-250, por defecto 50) |
| `timezone` | str (por defecto `Europe/Madrid`) |

Salida: `{ events: [{id, title, start, end, location, attendees, status, is_all_day, html_link}], next_page_token, timezone }`.

### `calendar.create_event` — v1.0.0

Crea una cita en el calendario del usuario.

- `read_only: false`, `idempotent: true` (con `idempotency_key`), `requires_confirmation: true`
- Permiso: `calendar.write` · Clasificación: `personal`
- Efectos: escritura en Google Calendar.

| Entrada | Tipo |
|---|---|
| `title` | str |
| `start` | datetime |
| `end` | datetime |
| `calendar_id` | str (opcional) |
| `description` / `location` | str (opcional) |
| `attendees` | list[email] (opcional) |
| `all_day` | bool |
| `timezone` | str |
| `send_notifications` | bool |
| `recurrence_rrule` | str (opcional) |
| `idempotency_key` | str |

Salida: `{ event_id, html_link, status, start, end, created, deduplicated }`.

---

## Documentos

Almacenamiento en el VPS en el MVP (S3/MinIO en v2). Validación de tipo real con `python-magic`. Ver [`07-security.md`](07-security.md).

### `documents.extract_invoice` — v1.0.0

Extrae datos estructurados de una factura o albarán en PDF.

- `read_only: true`, `idempotent: true`
- Permiso: `documents.read` · Clasificación: `business`
- Procesadores: `pdfplumber` / `markitdown`; OCR (`Tesseract`) si es escaneado.
- Si la confianza es baja, `needs_review: true`.

| Entrada | Tipo |
|---|---|
| `document_id` | UUID (subido previamente) |
| `document_type` | enum: `invoice`, `delivery_note`, `budget` |
| `language` | str (opcional) |

Salida: `{ issuer, issuer_cif, number, date, due_date, lines: [...], base, vat, total, currency, needs_review, confidence }` + `metadata.processor`.

### `documents.generate_invoice` — v1.0.0

Genera una factura o albarán en PDF mediante un renderizador HTML → PDF inyectable.

- `read_only: false`, `idempotent: true` (con `idempotency_key`), `requires_confirmation: true`
- Permiso: `documents.write` · Clasificación: `business`
- Efectos: calcula totales, reserva número y guarda el PDF a través de `DocumentStore`.

| Entrada | Tipo |
|---|---|
| `client` | ClientInput |
| `lines` | list[LineInput] |
| `number` | str (opcional; si falta, se propone) |
| `series` | str (opcional) |
| `date` / `due_date` | date |
| `vat_rate` | Decimal |
| `document_type` | enum: `invoice`, `delivery_note` |
| `currency` | str |
| `notes` / `payment_terms` | str (opcional) |
| `idempotency_key` | str |

Salida: `{ document_id, invoice_id, pdf_path, number, date, due_date, base, vat, total, currency, document_type, deduplicated }`.

---

## Alertas

### `alerts.contract_renewal` — v1.0.0

Programa recordatorios de renovación de contratos a 60/30/15 días.

- `read_only: false`, `idempotent: true` (con `idempotency_key`), `requires_confirmation: true`
- Permiso: `alerts.write` · Clasificación: `business`
- Efectos: crea `AlertRule`; no envía notificaciones en el MVP (solo registra eventos).

| Entrada | Tipo |
|---|---|
| `contract_id` | UUID |
| `renewal_date` | date (hoy o futura) |
| `notice_days` | list[int] (1-365, por defecto `[60, 30, 15]`) |
| `channel` | enum: `none`, `email`, `whatsapp` |
| `idempotency_key` | str |

Salida: `{ alert_rule_id, renewal_date, next_trigger_at, schedule: [{days_before, trigger_at, channel, status}], deduplicated }`.

---

## Backlog documentado

Herramientas previstas para la comunidad, con estado `backlog` (sin fecha) o `v2`. No se implementan en el MVP; sirven de guía y deben cumplir los criterios de entrada de [`02-mvp-scope.md`](02-mvp-scope.md#criterios-de-entrada-para-herramientas-de-backlog). Las specs completas están en el [índice de herramientas](tools/README.md).

| Categoría | Ejemplos | Estado |
|---|---|---|
| Energía | PVPC/OMIE horario, horas baratas, simulador de tarifa, optimizador de potencia, autoconsumo, huella de carbono | v2 |
| Tesorería | previsor 13 semanas, escenarios de estrés, DSO/DPO/DIO, cash conversion cycle, factoring | v2 |
| Finanzas empresa | EBITDA, cash flow, break-even, ratios, presupuestos vs. real, KPIs con semáforos | v2 |
| Compras | detector de subidas anómalas, RFP centralizada, registro de ahorro, renovaciones unificadas | v2 |
| Legal/regulatorio | concursos (BORME/Registro Concursal), lista de morosos, convenio colectivo, indemnización, obligaciones por CNAE | v2 |
| RR. HH. | vacaciones, absentismo, coste laboral, rotación | backlog |
| ESG | huella de carbono, intensidad energética, residuos, informe ESG | backlog |
| Estadística | media/mediana/moda, desviación, correlación, regresión, CAGR, anomalías | backlog |
| Marketing/ventas | CAC, LTV, churn, MRR/ARR, ROI de campaña, NPS | backlog |
| Operaciones/calidad | OEE, tasa de defectos, rotación de inventario, punto de pedido, stock de seguridad | backlog |
| Utilidades | QR, auditoría web (WHOIS/SSL), subvenciones (BDNS), imágenes de producto | backlog |
| Simuladores | rentabilidad solar, contratación de comercial → `praxis-sim` | v2 |

El catálogo completo aspiracional (energía, tesorería, RR. HH., ESG, etc.) se mantiene como referencia en el repositorio de `praxis-knowledge` cuando exista.
