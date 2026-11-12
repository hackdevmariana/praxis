# ADR-003: RLS de PostgreSQL para aislamiento multi-tenant

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

PRAXIS es multi-tenant desde el primer momento y aspira a ser adoptado por gestores, centrales de compras y asociaciones. Un filtro manual por `company_id` en cada consulta es propenso a errores y a fugas de datos.

## Decisión

Usar **Row-Level Security** de PostgreSQL como mecanismo principal de aislamiento.

- Todas las tablas tenant-scoped llevan `company_id NOT NULL` y RLS.
- Cada conexión fija `app.company_id` desde el `ToolContext`.
- Sin contexto, las tablas tenant niegan el acceso (deny by default).
- Las tablas globales no tienen política.

## Consecuencias

- Defensa en profundidad contra fugas entre tenants.
- Obliga a que **todas** las entidades de tenant tengan `company_id` (incluidas auditoría, consentimiento, scoring, notificaciones y credenciales).
- Requiere tests de integración con PostgreSQL real (`testcontainers`).
- El borrado GDPR por empresa es limpio y verificable.
