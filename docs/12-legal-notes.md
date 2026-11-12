---
estado: borrador
version: 0.1.0
---

# Notas legales (España)

> **Aviso:** este documento es un borrador de trabajo. **No constituye asesoramiento jurídico.** Todas las referencias normativas deben ser validadas por un profesional antes de usarse en producción. PRAXIS devuelve «señales para revisar», no dictámenes.

## Principio de producto

- Las herramientas legales, fiscales y laborales marcan `legal_disclaimer_required: true`.
- El resultado es orientativo y cita la norma aplicada (`LegalNorm`, `RuleParameter`).
- Las reglas son **versionadas** con `valid_from` / `valid_until`: nunca se sobrescribe una norma vigente sin trazabilidad.

## Protección de datos (RGPD/LOPDGDD)

Ver [`07-security.md`](07-security.md). Puntos a validar con abogado:

- Base jurídica por tratamiento y textos de consentimiento (`DataConsent`).
- Plazos de conservación por categoría de dato.
- Encargados de tratamiento (APIs externas) y transferencias internacionales.
- Registro de actividades de tratamiento y evaluación de impacto si aplica.
- Derecho al olvido: borrado por `company_id` y anonimización de `AuditLog`.

## Obligaciones de facturación y fiscales

| Materia | Referencia a validar | Uso en PRAXIS |
|---|---|---|
| IVA (tipos y modelos) | Ley 37/1992, AEAT | `finance.vat`, `TaxRate`, calendario fiscal |
| IRPF y retenciones | AEAT | Herramientas de retenciones (backlog) |
| Impuesto de sociedades | Ley 27/2014 | Backlog |
| Facturación electrónica / Verifactu | Reglamento AEAT | Estratégico v2, no MVP |
| SII (Suministro Inmediato de Información) | AEAT | v2 |
| Calendario fiscal (modelos 303, 111, 200) | AEAT + BOE | `FiscalCalendarRule`, `CompanyTaxObligation` |

Notas:

- El calendario fiscal debe distinguir regla general (global) de estado de la empresa (tenant).
- Los tipos impositivos se versionan y citan su fuente (`source_url` al BOE).

## Seguros

- **Ley 50/1980**, modificada por la **Ley 3/2023** (en vigor desde marzo de 2024):
  - La aseguradora debe avisar de la próxima renovación con **2 meses** de antelación.
  - El asegurado puede no renovar comunicándolo con al menos **1 mes** de antelación.
- Uso: `alerts.contract_renewal` con 60/30/15 días. **Validar** alcance y excepciones.

## Contratos y cláusulas

| Ámbito | Norma a validar | Uso |
|---|---|---|
| Arrendamientos urbanos | LAU (Ley 29/1994) | Detección de cláusulas de renovación/subida |
| Condiciones generales entre empresas | LCGC (Ley 7/1998) | Señales de cláusulas abusivas |
| Consumidores | TRLGDCU (RDL 1/2007) | Señales de cláusulas abusivas |

PRAXIS señala cláusulas a revisar; no emite juicio de legalidad definitivo.

## Laboral

| Materia | Referencia a validar | Uso |
|---|---|---|
| Estatuto de los Trabajadores | RDL 2/2015 | Despidos, preavisos, jornada |
| Indemnización por despido | Normativa y jurisprudencia vigente | Cálculo orientativo |
| Convenios colectivos | REGCON / BOE | Convenio aplicable por CNAE + provincia |
| Preaviso de baja/renuncia | Convenio aplicable | Cálculo orientativo |
| Obligaciones por actividad (CNAE) | Normativa sectorial/autonómica | Checklist, backlog |

Indemnizaciones (orientativas, a validar):

- Despido improcedente posterior al 12/02/2012: 33 días/año, tope 24 mensualidades.
- Despido improcedente con contrato anterior al 12/02/2012: 45 días/año hasta esa fecha + 33 días/año después; topes 42 y 24 mensualidades.
- Despido objetivo: 20 días/año, tope 12 mensualidades.

Estos parámetros se modelan como `RuleParameter` versionados, no como constantes en código.

## Mercantil y riesgo comercial

- **BORME**: cambios de administrador y actos registrales.
- **Registro Público Concursal / BOE**: situación de concurso.
- **Lista de morosos de Hacienda**: consulta pública.
- Uso: señales de riesgo al facturar o contratar. **Validar** condiciones de uso y fuentes.

## Redistribución de datos de terceros

- Cada instalación debe cumplir los términos de cada API (ver [`06-external-apis.md`](06-external-apis.md)).
- Si un proveedor no permite redistribución, no se cachea de forma compartida ni se reexpone fuera de la ejecución.
- La licencia MIT del software no cubre los datos de terceros.

## Tareas pendientes de validación

- [ ] Revisión legal completa de este documento.
- [ ] Textos de consentimiento y política de privacidad.
- [ ] Plazos de retención definitivos.
- [ ] Validación de referencias normativas y versiones vigentes.
- [ ] Condiciones de uso de fuentes públicas (BORME, Registro Concursal, lista de morosos).
- [ ] Alcance real de Verifactu/SII antes de implementar facturación electrónica.
