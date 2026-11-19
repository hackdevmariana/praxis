# ADR-008: Ingesta manual de datos de empresa en el MVP

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

Las herramientas de datos de empresa (KPIs, comparativas, tesorería) necesitan datos contables. Integrar conectores (Holded, Contasimple, banca PSD2) en 4 semanas es inviable y añade coste de mantenimiento y cumplimiento.

## Decisión

En el MVP, los datos de la empresa se almacenan en el backend a partir de **ingesta manual** (CSV/Excel/subida). Los conectores contables y bancarios se posponen a v2.

## Consecuencias

- Menor alcance y riesgo en el MVP.
- Los cálculos de KPIs, EBITDA, break-even y tesorería con datos aportados están disponibles desde v2; el cálculo sobre datos contables conectados sigue pendiente de los conectores, salvo las comparativas que no dependen de contabilidad (ofertas, TPV).
- `praxis-biz` se diseña con una abstracción de ingesta que permita añadir conectores sin rehacer el modelo.
- Se documenta el formato de importación y la validación de datos.
