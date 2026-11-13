---
estado: MVP
version: 0.1.0
---

# Especificaciones de herramientas

Un fichero por herramienta. El path refleja el nombre de la tool: `finance/vat.md` ↔ `finance.vat`.

Estas specs son **SDD**: describen el contrato y la semántica exacta antes de escribir código. Cuando exista la implementación, los golden tests (generados desde aquí) impiden la deriva.

## Convenciones

- **Idioma:** castellano; nombres de tool y campos en inglés.
- **Dinero:** `Decimal` serializado como **string**; redondeo `ROUND_HALF_UP` a 2 decimales salvo indicación.
- **Fechas:** ISO 8601; zona horaria por defecto `Europe/Madrid`.
- **Errores:** código estable + mensaje; ver tabla de errores MCP en [`../09-mcp.md`](../09-mcp.md).
- **Estado:** `MVP` (se implementa en la fase 1), `v2` o `backlog`.
- **Profundidad:** plantilla completa para MVP/v2; versión ligera (semántica + contrato + casos) para `backlog`.

## Plantilla

Cada spec incluye estas secciones, en este orden:

1. **Metadatos** — versión, permisos, clasificación, `read_only`/`idempotent`/`requires_confirmation`, provider, caché, perfiles de tenant.
2. **Semántica exacta** — fórmulas, reglas de redondeo y comportamiento en bordes.
3. **Contrato Pydantic** — `Input` y `Output` con tipos, constraints y defaults.
4. **Matriz de casos** — feliz / límite / error con resultado esperado.
5. **Golden cases** — pares `entrada JSON → salida exacta` (base de los tests).
6. **Metadatos de respuesta** — `source`, `valid_until`, warnings típicos.
7. **Composiciones** — tools relacionadas y puentes a `praxis-sim`.
8. **Decisiones pendientes** — cuestiones abiertas antes de implementar.

### Esqueleto

```markdown
---
estado: MVP
version: 1.0.0
tool: dominio.accion
---

# `dominio.accion` — <título>

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `dominio.accion` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista |
| Caché | n/a |
| Perfiles | all |

## 2. Semántica exacta
...

## 3. Contrato Pydantic
...

## 4. Matriz de casos
...

## 5. Golden cases
...

## 6. Metadatos de respuesta
...

## 7. Composiciones
...

## 8. Decisiones pendientes
...
```

## Índice

### MVP

| Tool | Spec |
|---|---|
| `validate.spanish_id` | [`validate/spanish_id.md`](validate/spanish_id.md) |
| `validate.iban` | [`validate/iban.md`](validate/iban.md) |
| `validate.email_phone` | [`validate/email_phone.md`](validate/email_phone.md) |
| `units.convert` | [`units/convert.md`](units/convert.md) |
| `datetime.calc` | [`datetime/calc.md`](datetime/calc.md) |
| `datetime.business_days` | [`datetime/business_days.md`](datetime/business_days.md) |
| `calendar.deadline_remaining` | [`calendar/deadline_remaining.md`](calendar/deadline_remaining.md) |
| `finance.vat` | [`finance/vat.md`](finance/vat.md) |
| `finance.margin` | [`finance/margin.md`](finance/margin.md) |
| `finance.discounts` | [`finance/discounts.md`](finance/discounts.md) |
| `finance.loan_schedule` | [`finance/loan_schedule.md`](finance/loan_schedule.md) |
| `currency.convert` | [`currency/convert.md`](currency/convert.md) |
| `weather.forecast` | [`weather/forecast.md`](weather/forecast.md) |
| `geo.geocode` | [`geo/geocode.md`](geo/geocode.md) |
| `procurement.tpv_savings` | [`procurement/tpv_savings.md`](procurement/tpv_savings.md) |
| `procurement.compare_offers` | [`procurement/compare_offers.md`](procurement/compare_offers.md) |
| `calendar.list_events` | [`calendar/list_events.md`](calendar/list_events.md) |
| `calendar.create_event` | [`calendar/create_event.md`](calendar/create_event.md) |
| `documents.extract_invoice` | [`documents/extract_invoice.md`](documents/extract_invoice.md) |
| `documents.generate_invoice` | [`documents/generate_invoice.md`](documents/generate_invoice.md) |
| `alerts.contract_renewal` | [`alerts/contract_renewal.md`](alerts/contract_renewal.md) |

### Extras v2

| Tool | Spec |
|---|---|
| `energy.pvpc_hourly` | [`energy/pvpc_hourly.md`](energy/pvpc_hourly.md) |
| `energy.cheapest_hours` | [`energy/cheapest_hours.md`](energy/cheapest_hours.md) |
| `energy.tariff_simulator` | [`energy/tariff_simulator.md`](energy/tariff_simulator.md) |
| `energy.self_consumption_payback` | [`energy/self_consumption_payback.md`](energy/self_consumption_payback.md) |
| `energy.carbon_footprint` | [`energy/carbon_footprint.md`](energy/carbon_footprint.md) |
| `finance.business_kpi` | [`finance/business_kpi.md`](finance/business_kpi.md) |
| `finance.ebitda` | [`finance/ebitda.md`](finance/ebitda.md) |
| `finance.cashflow_13w` | [`finance/cashflow_13w.md`](finance/cashflow_13w.md) |
| `finance.break_even` | [`finance/break_even.md`](finance/break_even.md) |
| `procurement.detect_price_increase` | [`procurement/detect_price_increase.md`](procurement/detect_price_increase.md) |
| `procurement.savings_ledger` | [`procurement/savings_ledger.md`](procurement/savings_ledger.md) |
| `procurement.rfp_generation` | [`procurement/rfp_generation.md`](procurement/rfp_generation.md) |
| `procurement.renewal_calendar` | [`procurement/renewal_calendar.md`](procurement/renewal_calendar.md) |
| `legal.company_risk` | [`legal/company_risk.md`](legal/company_risk.md) |
| `legal.collective_agreement` | [`legal/collective_agreement.md`](legal/collective_agreement.md) |
| `legal.severance_calc` | [`legal/severance_calc.md`](legal/severance_calc.md) |

### Backlog

Pendientes de redacción ligera (W9e). Se añaden aquí a medida que se especifican.

## Referencias

- Catálogo general: [`../03-tools-catalog.md`](../03-tools-catalog.md)
- Guía de autoría: [`../16-tool-authoring.md`](../16-tool-authoring.md)
- Contrato de respuesta: [`../08-formatting.md`](../08-formatting.md)
- Versionado: [`../17-versioning.md`](../17-versioning.md)
