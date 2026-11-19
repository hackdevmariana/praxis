---
estado: MVP
version: 0.1.0
---

# Métricas de éxito

PRAXIS se mide por **fiabilidad y ahorro**, no por número de herramientas.

## Objetivos del producto

| Objetivo | Métrica | Meta MVP |
|---|---|---|
| Evitar alucinaciones | % de ejecuciones deterministas con resultado verificable | 100 % de tools deterministas |
| Ahorro de tokens | Tokens medios por operación frente a resolución con LLM | Reducción ≥ 60 % en tools frecuentes |
| Trazabilidad | % de respuestas con metadatos completos | 100 % |
| Aislamiento | Fugas entre tenants detectadas en tests | 0 |
| Adopción | Tenants activos y tools usadas/semana | 3 tenants, ≥ 5 tools |

## Métricas de fiabilidad

- **Tasa de éxito por tool** (`success: true` / total).
- **Tasa de fallback por proveedor** y **tasa de `partial_result`**.
- **Cobertura de golden tests** por tool (caso feliz, límite, error).
- **Tasa de `needs_review`** en extracción de documentos.
- **Discrepancias de cálculo** detectadas en revisión (debe tender a 0; cada una genera test).

## Métricas de ahorro de tokens

- **Tokens por operación** (entrada/salida) en modo `json` vs. `compact`.
- **Ratio de uso de `summary`** frente a reescritura por LLM.
- **Número de llamadas por operación**: 1 llamada a tool vs. varias llamadas a LLM.
- **Tamaño medio de respuesta** por tool (bytes/ tokens).
- **Tasa de selección correcta de tool** por el LLM (evita reintentos y tokens perdidos).

## Métricas de rendimiento

- Latencia p50/p95 por tool y por proveedor.
- Ratio de cache hit (global y operacional).
- Llamadas externas por minuto vs. límites del proveedor.
- Disponibilidad de la API y del servidor MCP.

## Métricas de adopción

- Tenants activos por `catalog_key` (`hotel`, `poligono`, `asociacion`, más `general` por defecto).
- Tools más usadas por perfil.
- Usuarios activos por empresa.
- Alertas generadas y atendidas.
- Documentos procesados y facturas generadas.

## Métricas de negocio (diferencial)

- **Ahorro calculado** por `procurement.tpv_savings` y comparador de ofertas.
- **Renovaciones evitadas o renegociadas** a partir de alertas.
- **Tiempo ahorrado** estimado en tareas repetitivas.

## Evaluación de selección de tools (v2)

Cuando exista capa de canal/routing:

- **Accuracy** de selección de tool sobre un set de frases reales.
- **Confianza media** por nivel (regex/fuzzy/semantic/LLM).
- **Tasa de fallback a LLM** (cuanto menor, más ahorro).
- **Falsos positivos** de intención (deben ser 0 en tools con efectos).

## Cuadro de mando mínimo

| Dimensión | Indicador | Frecuencia |
|---|---|---|
| Fiabilidad | éxito por tool, fallback, warnings | Diaria |
| Ahorro | tokens/operación, selección correcta | Semanal |
| Rendimiento | latencia p95, cache hit | Diaria |
| Adopción | tenants, tools/semana | Semanal |
| Negocio | ahorro calculado | Mensual |

Los datos salen de `ToolExecutionLog` (`tool_execution_logs`; ver modelos en [`05-data-models.md`](05-data-models.md)). `UsageRecord` es un modelo previsto para planes SaaS, aún no implementado.
