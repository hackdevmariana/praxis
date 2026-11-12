# ADR-007: `praxis-sim` como vertical de simuladores

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

Consultas complejas (rentabilidad de placas solares, contratación de un comercial) combinan varias fuentes y cálculos. No encajan como tool atómica del core ni como conocimiento puro. Meterlos en `praxis-knowledge` mezclaría datos con lógica de orquestación.

## Decisión

Crear una vertical específica, `praxis-sim`, que contiene **pipelines y simuladores compuestos versionados**. Cada simulador:

1. Declara entradas y las tools atómicas que orquesta.
2. Ejecuta cada paso conservando metadatos intermedios.
3. Devuelve un resultado compuesto con trazabilidad de cada cálculo y fuente.

No duplica lógica de cálculo: la compone a partir de `praxis-core`.

## Consecuencias

- El LLM solo redacta el informe final; nunca calcula.
- Los simuladores son auditables y versionables por separado.
- `praxis-knowledge` se mantiene como fuente de contexto y normas, sin lógica operativa.
- Los simuladores quedan en v2; se documentan desde ya para no acoplar el core.
