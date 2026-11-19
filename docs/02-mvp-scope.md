---
estado: MVP
version: 0.1.0
---

# Alcance del MVP

Este documento define qué se construyó, en qué orden y qué queda fuera. El MVP se ejecutó con el objetivo de demostrar valor real en **4 semanas** con un único desarrollador, sobre una base escalable y documentada; el estado actual está resumido en `README.md` y `TODO.md`.

## Fases

| Fase | Objetivo | Entregable |
|---|---|---|
| **Fase 0 — Documentación (completada)** | Cerrar arquitectura, modelos, catálogo y compatibilidades antes de codificar. | `docs/` completo y coherente (42 specs). |
| **Fase 1 — MVP (completada)** | Implementar 21 herramientas y el servidor MCP con multi-tenancy. | Backend ejecutable + tests (verificado). |
| **Fase 2 — v2 (en curso)** | Conectores, routing semántico, canal WhatsApp/Telegram, simuladores. | Finanzas determinista implementada; backlog priorizado. |
| **Fase 3 — Futuro** | C-Level completo, SaaS por planes, comunidad de herramientas. | Roadmap abierto. |

> En esta tabla, Fase 2/3 significan el roadmap de producto. `TODO.md` usó “Fase 2” para persistencia y “Fase 3” para cierre de decisiones; ambos hitos están completados y ahora usa “Fase 2 — v2” para el roadmap.

## Herramientas del MVP

21 herramientas, agrupadas por tipo. `Tipo` distingue determinista puro (`det`), con datos externos (`ext`) y de negocio (`biz`). `Perfil` indica el tenant que la usa de forma prioritaria (`all` = todos).

| # | Tool | Tipo | Perfil | Semana |
|---|---|---|---|---|
| 1 | `datetime.calc` (hoy, mañana, diferencias, plazos) | det | all | 1 |
| 2 | `datetime.business_days` (días hábiles con festivos) | det | all | 1 |
| 3 | `calendar.deadline_remaining` (cierre mes/trimestre/año) | det | all | 1 |
| 4 | `finance.vat` (extraer, sumar, restar IVA) | det | all | 1 |
| 5 | `finance.margin` (margen y markup) | det | all | 1 |
| 6 | `finance.loan_schedule` (cuota y cuadro de amortización) | det | all | 1 |
| 7 | `finance.discounts` (descuentos sucesivos y precio original) | det | all | 1 |
| 8 | `validate.spanish_id` (NIF/CIF/NIE) | det | all | 1 |
| 9 | `validate.iban` | det | all | 1 |
| 10 | `validate.email_phone` | det | all | 1 |
| 11 | `units.convert` | det | all | 1 |
| 12 | `currency.convert` (BCE) | ext | all | 2 |
| 13 | `weather.forecast` (Open-Meteo) | ext | hotel, poligono | 2 |
| 14 | `geo.geocode` (CartoCiudad) | ext | all | 2 |
| 15 | `procurement.tpv_savings` (ahorro de comisiones TPV) | biz | asociacion | 3 |
| 16 | `procurement.compare_offers` (2-5 presupuestos → tabla normalizada) | biz | asociacion | 3 |
| 17 | `calendar.list_events` (OAuth por usuario) | biz | all | 3 |
| 18 | `calendar.create_event` (con confirmación humana) | biz | all | 3 |
| 19 | `documents.extract_invoice` (PDF → JSON) | biz | all | 3 |
| 20 | `documents.generate_invoice` (HTML → PDF) | biz | hotel, poligono | 4 |
| 21 | `alerts.contract_renewal` (60/30/15 días) | biz | asociacion, poligono | 4 |

> Las semanas son orientativas y se solapan. La semana 4 incluye además integración MCP, RLS, seeders mínimos y los escenarios de aceptación.

### Herramientas documentadas pero fuera del MVP

Sus specs completas (42 en total: 21 MVP, 18 v2 —4 implementadas— y 3 backlog) están en el [índice de herramientas](tools/README.md); [`03-tools-catalog.md`](03-tools-catalog.md) ofrece un resumen por categoría y los criterios de entrada. Incluyen:

- **Energía:** PVPC/OMIE horario, horas más baratas, simulador de tarifa, optimizador de potencia, autoconsumo, huella de carbono.
- **Tesorería y finanzas:** previsor a 13 semanas, escenarios de estrés, DSO/DPO/DIO, cash conversion cycle, factoring.
- **Datos de empresa avanzados:** EBITDA, cash flow, break-even, ratios, KPIs con semáforos, presupuestos vs. real.
- **Compras:** detector de subidas anómalas, RFP centralizada, registro de ahorro, calendario de renovaciones unificado.
- **Legal/regulatorio:** concursos (BORME/Registro Concursal), lista de morosos, convenio colectivo, indemnización por despido, obligaciones por CNAE.
- **RR. HH., ESG, estadística, analítica, marketing, operaciones y calidad** (ideas de backlog sin spec aún).
- **Utilidades:** QR, auditoría web (WHOIS/SSL) y subvenciones (BDNS).
- **Simuladores compuestos:** rentabilidad de placas solares, simulador de contratación de comercial → `praxis-sim` (v2).

## Fuera de alcance explícito

| Elemento | Decisión | Motivo |
|---|---|---|
| ESIOS/OMIE (precio horario) | v2 | Token personal solicitado por email; latencia de alta |
| semantic-router / gateway WhatsApp | v2 | Capa de canal externa al core |
| Billing / planes / suscripciones | backlog | El MVP no se comercializa como SaaS |
| Conectores contables (Holded, etc.) | v2 | Ingesta manual en MVP |
| Almacenamiento S3/MinIO | v2 | Documentos en el VPS en MVP |
| OIDC / Keycloak | v2 | API key + JWT simple en MVP |
| Generación de presentaciones, landings y webs | futuro | Requiere LLM externo; fuera del perímetro determinista |
| RR. HH. completo, ESG, simuladores | v2 / futuro | Alto coste de integración y datos |

## Criterios de entrada para herramientas de backlog

Una herramienta nueva (interna o de la comunidad) entra al catálogo cuando cumple los 8 puntos:

1. **Fuente determinista o externa verificable.** No depende de un LLM para producir el resultado.
2. **Esquema cerrado.** Entrada y salida tipadas con Pydantic; JSON Schema generable.
3. **Metadatos completos.** Fuente, `retrieved_at`, `valid_until`, unidad, moneda, zona horaria, `is_estimated`, errores.
4. **Clasificación de datos.** `public | business | personal | sensitive` y permisos requeridos.
5. **Read-only o efectos declarados.** Si escribe, `idempotent` e `idempotency_key`; si es sensible, `requires_confirmation`.
6. **Golden tests.** Al menos un caso feliz, un caso límite y un caso de error.
7. **Ficha de proveedor.** Si usa API externa: rate limits, ToS, fallback y caché.
8. **Versión y deprecación.** SemVer, `replaced_by` si aplica.

## Definición de hecho del MVP

El MVP se considera terminado cuando los tres escenarios siguientes funcionan de extremo a extremo a través del servidor MCP:

1. **Hotel — agenda:** el agente consulta la agenda del gerente y crea una cita con confirmación humana, sin mezclar eventos personales y de empresa.
2. **CEO/Polígono — finanzas y documentos:** el agente calcula el IVA de un importe, extrae los datos de una factura en PDF y compara varios presupuestos en una tabla normalizada.
3. **Asociación — compras:** el agente calcula el ahorro anual de comisiones TPV y programa una alerta de renovación de contrato a 60/30/15 días.

Cada escenario debe devolver JSON con metadatos completos y quedar registrado en el log de ejecuciones con empresa, usuario, versión de tool y fuente.

## Roadmap resumido

| Fase | Contenido |
|---|---|
| **v2** | Finanzas determinista (implementada), conectores contables y bancarios (PSD2), ESIOS/OMIE, routing semántico, gateway WhatsApp/Telegram, `praxis-sim`, S3, OIDC, simulador de decisión. |
| **Futuro** | C-Level completo, planes SaaS con catálogo por `TenantProfile`, marketplace de herramientas comunitarias, ESG, análisis de competencia/SEO, generación de contenidos con modelo mixto. |
