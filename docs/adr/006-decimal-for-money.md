# ADR-006: Decimal para dinero

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

Los cálculos financieros y fiscales exigen exactitud al céntimo. `float` introduce errores de representación. Algunas librerías financieras (`numpy-financial`) operan en `float64`.

## Decisión

- Usar `Decimal` para todos los importes y tipos impositivos.
- Serializar importes como **string decimal** en JSON.
- Redondear con `ROUND_HALF_UP` a 2 decimales en los límites definidos.
- No se usa `numpy-financial` en el MVP; si se incorpora, documentar y testear el boundary `Decimal → float → Decimal`, con cuadre al céntimo.

## Consecuencias

- Resultados reproducibles y auditables.
- Cambios de contrato si alguna tool usó `float` (requieren MAJOR; ver ADR de versionado).
- Necesidad de tests específicos de redondeo y de cuadre en cuadros de amortización.
