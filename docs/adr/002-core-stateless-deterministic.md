# ADR-002: Core stateless y determinista

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

El objetivo es evitar alucinaciones y ahorrar tokens. Mezclar NLP, routing semántico y formateo conversacional dentro del motor de cálculo introduciría no determinismo y acoplamiento.

## Decisión

`praxis-core` es un motor **casi stateless y determinista**. Recibe argumentos tipados, ejecuta lógica determinista o consulta APIs externas y devuelve JSON + metadatos. No contiene NLP, semantic-router ni plantillas conversacionales. Hoy se materializa en este repositorio como el paquete `app/`, con stores SQLAlchemy inyectables para idempotencia y control de acceso cuando hay `DATABASE_URL`.

Los datos de tenant, conocimiento y conectores viven en `praxis-biz` y `praxis-knowledge`.

## Consecuencias

- Resultados reproducibles y auditables.
- Escalado horizontal sencillo al no mantener estado de conversación.
- El routing y el formateo se delegan a una capa de canal externa.
- Toda dependencia de estado de empresa debe pasar por el contexto (`ToolContext`) y `praxis-biz`.
