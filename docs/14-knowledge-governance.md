---
estado: MVP
version: 0.1.0
---

# Gobernanza de la base de conocimiento

`praxis-knowledge` contiene dos capas:

1. **Conocimiento genérico compartido:** economía, contabilidad, redacción, marketing y normativa. Curado, versionado y actualizable por la comunidad.
2. **Conocimiento por empresa (second-brain del CEO):** documentación privada del tenant. **Nunca** se versiona en git.

## LLM Wiki + Obsidian

El conocimiento genérico se mantiene como **LLM Wiki** curado con Obsidian, en un repositorio de GitHub independiente para que la comunidad lo mantenga.

- Documentos en Markdown con **frontmatter YAML** (`python-frontmatter`).
- Estructura pensada para lectura humana y para chunking automático.
- Cada entrada declara su vigencia, fuente y tipo.

### Frontmatter mínimo

```yaml
---
title: "Convenio colectivo de hostelería 2026"
source_type: regulatory      # generic | regulatory | municipal
license: CC-BY-4.0
valid_from: 2026-01-01
valid_until: 2026-12-31
is_authoritative: true
citation: "BOE núm. ..., de ..."
tags: [convenio, hostelería, laboral]
reviewed_by: "equipo-praxis"
last_reviewed_at: 2026-02-01
---
```

## El problema de la actualización

La legislación, la tributación y los convenios cambian. El sistema debe asumir la **caducidad** como parte del dato:

- Todo documento y regla tiene `valid_from` / `valid_until`.
- Se filtran resultados por vigencia en tiempo de consulta.
- Los datos caducados se marcan `metadata.warnings` y `is_estimated=false` con aviso explícito.
- Un job periódico detecta documentos próximos a caducar y los pone en revisión.

## Curación y autoridad

| Nivel | Descripción | Marca |
|---|---|---|
| Autoritativo | Fuente oficial (BOE, AEAT, ministerio) | `is_authoritative: true` |
| Curado | Interpretación revisada por humano | `is_curated: true` |
| Comunitario | Aportación sin revisión | pendiente de revisión |

- Lo comunitario no se sirve como autoritativo hasta pasar revisión.
- Cada chunk conserva `citation` y `metadata` (página, sección) para responder con referencias.

## Búsqueda híbrida

- **FTS** (`TSVECTOR`) para coincidencia literal y términos legales.
- **pgvector** (embeddings) para similitud semántica.
- Se combinan resultados y se prioriza por vigencia, autoridad y relevancia.
- El agente recibe fragmentos con su cita y metadatos, no el documento entero (ahorro de tokens).

## Capa privada por empresa

- La documentación de la empresa se ingesta con `company_id`.
- Vive en la base de datos de la instalación, **nunca** en el repositorio git.
- RLS garantiza que un tenant no accede al conocimiento de otro.
- El borrado GDPR elimina documentos, chunks y embeddings del tenant.
- El "second-brain del CEO" es la suma de documentos, decisiones y contexto privado de esa empresa.

## Separación con `praxis-core` y `praxis-sim`

- **Conocimiento** describe *qué dice la norma y el contexto*; no calcula.
- **Core** ejecuta cálculos deterministas; no interpreta normativa.
- **Sim** compone cálculos en pipelines; usa el conocimiento para parámetros, pero no lo sustituye.

## Proceso de contribución (comunidad)

1. Proponer un documento con frontmatter completo y fuente.
2. Revisión por mantenedores (autoridad, vigencia, licencia).
3. Añadir a índice y generar chunks/embeddings.
4. Registrar `reviewed_by` y `last_reviewed_at`.
5. Programar revisión por caducidad.

Ver [`16-tool-authoring.md`](16-tool-authoring.md) para contribuir con herramientas y [`17-versioning.md`](17-versioning.md) para versionar normas y tools.

## Licencias y atribución

- El software es MIT; el conocimiento puede tener su propia licencia por documento (`license` en frontmatter).
- Solo se aceptan fuentes redistribuibles.
- Se conserva la cita y el `source_url` para atribución.
