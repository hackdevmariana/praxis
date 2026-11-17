---
estado: MVP
version: 0.1.0
---

# Modelos de datos y dominios

Este documento consolida los dominios del backend, las correcciones de compatibilidad y las reglas de aislamiento multi-tenant. Los modelos definitivos viven en `praxis-biz` (datos de tenant) y `praxis-knowledge` (conocimiento); `praxis-core` es casi stateless.

## Convenciones

- **Base declarativa:** SQLAlchemy 2 (`DeclarativeBase`).
- **Identidad:** `UUID` (`uuid4`) como PK.
- **Timestamps:** `created_at`, `updated_at` con `DateTime(timezone=True)`.
- **Dinero:** `Decimal` (`Numeric(14,2)`); nunca `float` en columnas monetarias.
- **Tenant:** toda tabla de datos de empresa lleva `company_id UUID NOT NULL` salvo las globales (ver tabla siguiente).
- **Borrado GDPR:** `company_id` presente en todas las tablas tenant permite borrado limpio por empresa (`ON DELETE CASCADE` o borrado lógico revisado).
- **Clasificación de datos:** anotada por entidad (`public | business | personal | sensitive`).

## Global vs. tenant-scoped (RLS)

| Grupo | Tablas | `company_id` | RLS |
|---|---|---|---|
| Global compartido | `Location`, `EnergyPrice`, `DataSource`, `FiscalCalendarRule`, `LegalNorm`, `RuleParameter`, `TaxRate`, `KnowledgeSource` (genérica), `KnowledgeDocument` (genérica), `KnowledgeChunk` (genérica), `Plan` | No | No aplica |
| Tenant-scoped | `User`, `Company`, `Membership`, `TenantProfile`, `Client`, `Supplier`, `Contract`, `Order`, `Document`, `DocumentExtraction`, `DocumentComparison`, `Event`, `Task`, `CompanyTaxObligation`, `KPI`, `KPIThreshold`, `Budget`, `CashFlowProjection`, `Loan`, `AlertRule`, `AlertEvent`, `Notification`, `EnergyBill`, `EnergyConsumptionProfile`, `CarbonFootprint`, `Employee`, `Leave`, `PayrollEntry`, `Metric`, `AnomalyDetection`, `Score`, `Message`, `QRCode`, `AuditLog`, `DataConsent`, `Integration`, `IntegrationCredential`, `SyncLog`, `Subscription`, `UsageRecord`, `Invoice` | Sí | Sí |

> `User` no es estrictamente de una empresa (puede pertenecer a varias vía `Membership`), pero sus datos se filtran por las empresas a las que tiene acceso. Las entidades hijas de tenant (`Score`, `AuditLog`, `DataConsent`, `Notification`, `IntegrationCredential`, `SyncLog`, `Invoice`) **heredan** `company_id` para poder aplicar RLS y borrado GDPR.

### Implementación MVP de RLS

- La migración `0001_initial_rls` crea el esquema mínimo: `companies`, `tenant_profiles`, `tool_activations`, `idempotency_records` y la tabla global `data_sources`.
- Todas las tablas tenant llevan `company_id` (en `companies`, su `id` actúa como tal) y activan `ROW LEVEL SECURITY` con `FORCE ROW LEVEL SECURITY`.
- La política usa `current_setting('praxis.company_id', true)::uuid`. Si no hay contexto, la consulta no devuelve filas tenant.
- `app/db/rls.py` fija el valor con `set_config('praxis.company_id', :company_id, true)` dentro de la transacción; `company_session(engine, company_id)` es el único acceso recomendado.
- La migración crea el rol no superusuario `praxis_app` con permisos DML. Las pruebas de aislamiento se conectan con ese rol para que RLS no sea bypassado por el propietario/superusuario.
- `data_sources` es global y no lleva RLS; es visible desde cualquier contexto de empresa.

## Dominio 1 — Identity

```txt
User
  id, email, name, phone, language, timezone,
  last_active_company_id, is_active, mfa_enabled,
  preferred_channel, notification_preferences JSONB,
  onboarding_completed, trial_ends_at, created_at

Company
  id, name, cif, cnae, ine_code, province, municipality,
  address, postal_code, phone, email, website,
  association_id, created_at

Association
  id, name, domain, contact_email, active, created_at

Membership
  id, user_id, company_id, role,
  permissions_override JSONB, invited_by, invited_at, joined_at,
  status (active|invited|suspended|removed),
  UNIQUE(user_id, company_id)

CompanyInvitation
  id, email, company_id, role, token_hash,
  expires_at, invited_by, accepted_at

AssociationMembership
  id, user_id, association_id, role, status

TenantProfile
  id, company_id, catalog_key, region, locale,
  config JSONB, is_active, created_at
```

- `role`: `owner | admin | manager | viewer | employee | association_admin`.
- `TenantProfile.catalog_key` selecciona el conjunto de tools (`hotel`, `poligono`, `asociacion`, `general`). Ver [`09-mcp.md`](09-mcp.md).
- `Company.ine_code` (5 dígitos) es la llave maestra para cruzar INE, AEMET, Catastro y BDNS.

### API keys y permisos

```txt
ApiKey
  id, user_id, key_hash (Argon2id), scopes list[str],
  expires_at, last_used_at, is_active, created_at

Permission
  id, tool_name, role, can_read, can_write, requires_confirmation
```

- `ApiKey.key_hash` con `argon2-cffi` (Argon2id). Nunca se almacena la clave en claro.
- `Permission` referencia `tool_name` (no `tool_id`): el catálogo canónico está en código (ADR-004).

## Dominio 2 — Tool (catálogo)

La definición de herramientas **no** se edita en base de datos. El código con `@tool` es la fuente de verdad. La BD guarda solo lo operativo:

```txt
ToolActivation
  id, company_id, tool_name, version_installed,
  is_enabled, config JSONB, limits_override JSONB,
  deprecated BOOL, replaced_by TEXT, updated_at

ToolCatalog
  id, company_id, name, catalog_key,
  tool_names list[str], is_active
```

Se eliminan del modelo los campos canónicos (`input_schema`, `output_schema`, `description`...) como fuente editable: se generan desde el código. Sí se permiten `mcp_description_override` y `examples_override` por tenant si se necesitan.

Consumo y auditoría:

```txt
ToolExecutionLog
  id, request_id, tool_name, tool_version,
  user_id, company_id, channel,
  input_hash, input_params JSONB, output_data JSONB,
  execution_time_ms, execution_method,
  success, error, cache_hit, provider_calls JSONB,
  cost_actual NUMERIC(12,6), idempotency_key,
  partial_result, warnings JSONB, legal_disclaimer_shown,
  created_at
```

## Dominio 3 — Execution

```txt
ExecutionRequest
  id, user_id, company_id, channel, message, language,
  response_mode, last_execution_context JSONB,
  agent_mode, idempotency_key, parent_request_id, created_at

ExecutionResult
  id, request_id, intent, execution_method, tool_name,
  data JSONB, display_text, metadata JSONB,
  requires_clarification, clarification_question,
  confidence, execution_time_ms, created_at

ConversationContext
  id, user_id, last_intent, last_params JSONB,
  last_result_summary, expires_at   # Redis TTL 5 min
```

## Dominio 4 — Data (fuentes y caché)

```txt
DataSource
  id, name, source_type, base_url, api_key_env,
  rate_limit_per_minute, rate_limit_per_day,
  cache_ttl_default, is_reliable, is_active,
  terms_of_service_url, redistribution_allowed,
  attribution_required, personal_data_collected,
  cost_per_call, fallback_source_id,
  circuit_breaker_state, circuit_breaker_failures,
  circuit_breaker_opened_at

DataCacheEntry       # metadatos; el valor vive en Redis
  id, source_id, cache_key, valid_until,
  is_estimated, confidence, unit, currency, timezone, created_at
```

`DataSource` es global. La caché compartida (clima, divisas) no lleva `company_id`; la operacional sí en la clave.

## Dominio 5 — Alert

```txt
AlertRule
  id, company_id, user_id, name, category, trigger_type,
  parameters JSONB, threshold, severity, is_active,
  last_triggered_at, created_at

AlertEvent
  id, company_id, rule_id, message, data JSONB, severity,
  acknowledged, acknowledged_by, created_at

Notification
  id, company_id, user_id, channel, message,
  alert_event_id, sent_at, delivered_at, status, created_at
```

## Dominio 6 — Document

```txt
Document
  id, company_id, user_id, name, type, format,
  storage_path, file_hash, file_size, language,
  extracted_data JSONB, metadata JSONB, is_processed, created_at

DocumentExtraction
  id, company_id, document_id, extraction_type,
  result JSONB, confidence, processor,
  extraction_version, language_detected,
  processing_time_ms, needs_review, created_at

DocumentComparison
  id, company_id, document_a_id, document_b_id,
  differences JSONB, created_at
```

`storage_path` apunta al VPS en el MVP (ADR-005). Validación de tipo real con `python-magic`.

## Dominio 7 — Energy

```txt
EnergyPrice          # global
  id, date, period, hour, market, price,
  currency, source, is_estimated, created_at

EnergyBill
  id, company_id, user_id, supplier, period_start, period_end,
  total_cost, energy_cost, tax_cost, fixed_cost, variable_cost,
  consumption_kwh, peak_demand_kw, tariff, qr_data JSONB,
  document_id, created_at

EnergyConsumptionProfile
  id, company_id, month, year, total_kwh,
  peak_kwh, valley_kwh, flat_kwh, peak_hour, valley_hour,
  flat_hour, max_demand_kw, created_at

CarbonFootprint
  id, company_id, period_start, period_end,
  energy_co2, transport_co2, waste_co2, total_co2,
  intensity, created_at
```

## Dominio 8 — Finance

```txt
KPI
  id, company_id, name, period, value, target,
  previous_value, variation_pct, signal, metadata JSONB, created_at

KPIThreshold
  id, company_id, kpi_name, green_min, green_max,
  yellow_min, yellow_max

Budget
  id, company_id, fiscal_year, department, category,
  item, planned, actual, variance, variance_pct, created_at

CashFlowProjection
  id, company_id, projection_date, opening_balance,
  expected_inflows, expected_outflows, closing_balance,
  scenario, created_at

Loan
  id, company_id, lender, principal, interest_rate,
  term_months, start_date, amortization_schedule JSONB,
  outstanding_balance, created_at
```

### Impuestos y normativa (global, versionado)

```txt
TaxRate
  id, tax_type, rate_name, rate_value,
  valid_from, valid_until, source_url, jurisdiction

LegalNorm
  id, code, title, category, jurisdiction, community,
  source_url, publication_date, valid_from, valid_until,
  is_active, created_at, updated_at

RuleParameter
  id, norm_id, parameter_key, parameter_value, unit,
  description, applies_to JSONB, valid_from, valid_until, is_active

FiscalCalendarRule
  id, norm_id, tax_type, model_name, period_type,
  deadline_day, deadline_month_offset,
  applies_to_cnae JSONB, applies_to_legal_form JSONB,
  jurisdiction, valid_from, valid_until, is_active

CompanyTaxObligation    # tenant
  id, company_id, rule_id, period, deadline,
  status (pending|filed|overdue), amount, filed_at, created_at
```

> **Corrección:** `FiscalDeadline` se divide en `FiscalCalendarRule` (global, regla legal) y `CompanyTaxObligation` (tenant, estado de una empresa). Así la regla se comparte y el estado se aísla por RLS.

## Dominio 9 — Business

```txt
Client
  id, company_id, name, cif, contact_name, email, phone,
  segment, annual_revenue, ltv, churn_risk,
  last_interaction, is_active, created_at

Supplier
  id, company_id, name, cif, category, contact_name, email, phone,
  current_contract_value, contract_renewal_date, rating,
  is_active, created_at

Contract
  id, company_id, counterparty, counterparty_cif, type,
  start_date, end_date, value, currency, renewal_type,
  renewal_notice_days, penalty_clause, document_id,
  is_active, created_at

Order
  id, company_id, client_id, supplier_id, type, order_number,
  date, total, status, items JSONB, created_at
```

## Dominio 10 — HR

```txt
Employee
  id, company_id, name, nif, position, department, hire_date,
  salary_gross, contract_type, hours_per_week, is_active, created_at

Leave
  id, company_id, employee_id, type, start_date, end_date,
  days, status, created_at

PayrollEntry
  id, company_id, employee_id, month, year, gross, net,
  social_security_employee, social_security_company,
  overtime_hours, overtime_cost, total_cost_company, created_at
```

`sensitive`: `nif`, `salary_gross`, `gross`, `net` (cifrado a nivel de campo, ver [`07-security.md`](07-security.md)).

## Dominio 11 — Geography

```txt
Location             # global
  id, name, municipality, province, community, postal_code,
  latitude, longitude, timezone, country, ine_code

Address
  id, company_id, line1, line2, municipality, province,
  postal_code, latitude, longitude, location_id
```

`Location` con PostGIS (`GEOGRAPHY(Point, 4326)`) e índice GiST para búsquedas por proximidad.

## Dominio 12 — Calendar

```txt
Event
  id, company_id, user_id, title, description,
  start_datetime, end_datetime, location, attendees JSONB,
  recurrence, is_all_day, google_event_id, calendar_id, created_at

Task
  id, company_id, user_id, title, description, due_date,
  priority, status, assignee_id, category, created_at, updated_at
```

`Event` refleja la agenda del usuario (OAuth por usuario). `calendar_id` distingue calendario personal y de empresa.

## Dominio 13 — Analytics

```txt
Metric
  id, company_id, name, category, formula, unit,
  period, value, metadata JSONB, created_at

AnomalyDetection
  id, company_id, metric_name, period, expected_value,
  actual_value, deviation_pct, z_score, is_anomaly, created_at

Score
  id, company_id, entity_type, entity_id, score,
  criteria JSONB, created_at
```

> **Corrección:** `Score` incluye `company_id` (faltaba) para RLS y borrado GDPR.

## Dominio 14 — Communication

```txt
Message
  id, company_id, user_id, channel, direction, content_type,
  content, media_url, transcript, transcript_confidence,
  execution_result_id, created_at

QRCode
  id, company_id, purpose, data, has_logo, image_path, created_at
```

## Dominio 15 — Compliance

```txt
AuditLog
  id, company_id, user_id, action, resource, resource_id,
  ip_address, user_agent, result, metadata JSONB, created_at

DataConsent
  id, company_id, user_id, purpose, granted,
  granted_at, revoked_at, created_at
```

> **Corrección:** `AuditLog` y `DataConsent` incluyen `company_id` (faltaba), imprescindible para RLS y para el derecho al olvido. `AuditLog` es append-only.

## Dominio 16 — Knowledge

```txt
KnowledgeSource
  id, source_type (generic|company|regulatory|municipal),
  company_id NULL, name, description, source_url, license,
  valid_from, valid_until, is_curated, curated_by,
  last_reviewed_at, created_at, updated_at

KnowledgeDocument
  id, source_id, company_id NULL, title, content,
  document_type, tags JSONB, valid_from, valid_until,
  is_authoritative, citation, created_at, updated_at

KnowledgeChunk
  id, document_id, content, chunk_index,
  embedding vector(1024), search_vector TSVECTOR,
  metadata JSONB, created_at
```

`company_id NULL` = conocimiento compartido. El conocimiento privado de empresa **nunca** se versiona en git. Ver [`14-knowledge-governance.md`](14-knowledge-governance.md).

## Dominio 17 — Integration / Connector

```txt
Integration
  id, company_id, provider, provider_type,
  status, account_label, scopes JSONB, connected_at,
  last_sync_at, sync_cursor, error_message, is_active,
  created_at, updated_at

IntegrationCredential
  id, company_id, integration_id, credential_type,
  encrypted_value BYTEA, expires_at, last_rotated_at, created_at

SyncLog
  id, company_id, integration_id, operation, status,
  items_processed, items_created, items_updated, items_failed,
  cursor_before, cursor_after, duration_ms, error, created_at
```

> **Corrección:** `IntegrationCredential` y `SyncLog` heredan `company_id` para RLS. Credenciales cifradas con sobre (envelope encryption) y rotación de claves.

## Dominio 18 — Billing / Quota

Fuera del MVP comercial. Se mantiene `UsageRecord` para cuotas y auditoría; `Plan`, `Subscription` e `Invoice` quedan como backlog.

```txt
UsageRecord
  id, company_id, metric, quantity, period, created_at
```

## Dominio 19 — Norm

Ver «Impuestos y normativa» en el Dominio 8 (`LegalNorm`, `RuleParameter`, `FiscalCalendarRule`). Separa norma global de obligación por empresa.

## Reglas transversales

### RLS (ejemplo)

```sql
ALTER TABLE document ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON document
  USING (company_id = current_setting('app.company_id')::uuid);
```

- Cada conexión fija `app.company_id` desde el `ToolContext`.
- Las tablas globales no tienen política; las tenant devuelven cero filas sin contexto.
- Los tests de integración con `testcontainers` verifican que sin `company_id` no se filtra nada.

### Índices y restricciones

- `UNIQUE(user_id, company_id)` en `Membership`.
- Índice en `ToolExecutionLog(company_id, created_at)` para auditoría.
- Índice GiST en `Location.geography`.
- Índice HNSW en `KnowledgeChunk.embedding` y GIN en `search_vector`.
- `UNIQUE(company_id, number)` en documentos generados.

### Cifrado de campos sensibles

`nif`, `salary_gross`, `gross`, `net`, `encrypted_value`, tokens OAuth: cifrado a nivel de campo con envelope encryption (`cryptography`), no `sqlalchemy-utils.EncryptedType`.
