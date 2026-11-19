---
estado: MVP
version: 0.1.0
---

# Versionado y deprecación

## Qué se versiona

| Elemento | Esquema | Dónde |
|---|---|---|
| Herramientas | SemVer `MAJOR.MINOR.PATCH` | `@tool(version=...)`, sobre de respuesta |
| Contrato MCP (nombre, esquema) | SemVer del conjunto | Catálogo MCP |
| Normas y reglas | Vigencia `valid_from`/`valid_until` | `LegalNorm`, `RuleParameter` |
| Datasets (seeders) | Fecha `YYYY-MM-DD` | Metadatos del seeder |
| Software PRAXIS | SemVer | Monorepo / releases |

## SemVer de herramientas

- **MAJOR:** cambio incompatible en entrada/salida o en semántica (p. ej. unidad de un campo, moneda por defecto, redondeo). Requiere nueva versión anunciada y periodo de coexistencia.
- **MINOR:** nueva funcionalidad retrocompatible (campos opcionales de salida, nuevas operaciones).
- **PATCH:** correcciones de cálculo sin cambiar el contrato, mejoras de metadatos, fixes de proveedor.

Reglas:

- El `name` no cambia con la versión.
- La versión viaja en `tool_version` del sobre, no en el nombre MCP.
- Los golden tests fijan la versión esperada.

## Deprecación

```python
# @tool no acepta deprecated/replaced_by (registry.tool):
@tool(name="finance.vat", version="1.3.0", ...)

# La deprecación se registra hoy por tenant:
ToolActivationRow(..., deprecated=True, replaced_by="tax.vat_calculate")
```

- La deprecación se registra en `tool_activations.deprecated`/`replaced_by` y excluye la tool del toolset del tenant. El anuncio MCP con flags de deprecación requiere soporte futuro.
- Se documenta la alternativa y la fecha de retirada.
- Periodo mínimo de coexistencia: **una versión MINOR** o **90 días** (lo que sea mayor) para herramientas públicas.
- La retirada exige un MAJOR del catálogo y notas de migración.

## Cambios incompatibles

Checklist antes de un MAJOR:

1. ADR o nota en el changelog que explique el motivo.
2. Nueva tool/versión disponible y probada.
3. Guía de migración (campos renombrados, unidades, redondeo).
4. `replaced_by` y `deprecated` en la activación de la anterior.
5. Actualización de catálogo, `intents.yaml` y documentación.
6. Tests de ambas versiones durante la coexistencia.

Nunca se rompe el contrato de una tool publicada sin MAJOR.

## Normas, reglas y datasets

- **Vigencia:** una norma no se sobrescribe; se cierra con `valid_until` y se crea una nueva con `valid_from`.
- **Parámetros:** `RuleParameter` versionado; las tools leen el vigente por fecha de la operación.
- **Seeders:** cada ejecución registra versión de dataset y `source`; son idempotentes y auditables.
- **Conocimiento:** frontmatter con `valid_from`/`valid_until` y `last_reviewed_at`.

## Compatibilidad MCP

- El servidor filtra las tools anunciadas y ejecutables según `ToolAccessPolicy`: con `DATABASE_URL`, `TenantProfile` y `ToolActivation` bajo RLS; sin BD, política inyectable.
- Una versión MCP se declara compatible si mantiene nombres y esquemas anunciados o si marca deprecación con antelación.
- Los clientes deben tolerar campos nuevos en la salida (additive changes).
- Los campos eliminados solo en MAJOR.

## Changelog

- Formato Keep a Changelog por release de software.
- Por herramienta, se documenta en su ficha del catálogo y en el changelog del monorepo.
- Incluye: añadido, cambiado, deprecado, eliminado, corregido y seguridad.

## Ejemplo de ciclo de vida

```txt
finance.vat 1.0.0  → estable; ya incluye operation="remove" y currency
                     y serializa importes Decimal como string
finance.vat 1.1.0  → ejemplo de cambio retrocompatible futuro
finance.vat 2.0.0  → ejemplo de cambio BREAKING futuro
                     + tax.vat_calculate 1.0.0 como reemplazo
finance.vat 1.1.0  → deprecada, coexistencia 90 días
```
