# ADR-005: Almacenamiento de documentos en el VPS (MVP)

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

El MVP debe gestionar documentos (facturas, albaranes) sin añadir la complejidad operativa de S3/MinIO ni depender de un proveedor cloud. El despliegue es self-hosted en un VPS.

## Decisión

En el MVP, los documentos se almacenan en el **sistema de archivos del VPS**, con nombres opacos (UUID) y ruta fuera del webroot. En v2 se migrará a S3/MinIO con URLs firmadas y cifrado en reposo.

## Consecuencias

- Simplicidad de despliegue y menores dependencias.
- Se debe validar el tipo real de archivo con `python-magic` y limitar tamaño.
- Requiere backups y política de retención propias.
- La abstracción de almacenamiento debe permitir cambiar a S3 sin tocar las tools.
