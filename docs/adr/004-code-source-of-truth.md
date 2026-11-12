# ADR-004: El código es la fuente de verdad de las herramientas

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

Definir las herramientas manualmente en base de datos (esquema, descripción, versión) genera divergencia con el código, Pydantic, JSON Schema, OpenAPI, MCP y documentación.

## Decisión

La definición canónica de una herramienta vive en el decorador `@tool` en código. De ahí se generan:

- JSON Schema de entrada/salida.
- Catálogo y anotaciones MCP.
- Documentación.
- Golden tests.

La base de datos guarda solo lo operativo: activación por tenant, overrides de descripción/ejemplos, límites, permisos concedidos, deprecaciones y versiones instaladas.

## Consecuencias

- Una sola fuente de verdad; menos deriva.
- Los contribuidores definen tools en código, con revisión de PR.
- La BD no permite editar esquemas que pertenecen al código.
- El catálogo publicado (`03-tools-catalog.md`) es un reflejo generado/navegable, no la fuente.
