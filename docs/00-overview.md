---
estado: MVP
version: 0.1.0
---

# PRAXIS — Visión general

## Qué es PRAXIS

PRAXIS es un sistema de herramientas empresariales en formato **API y MCP**, independiente del agente que las consulte. Su propósito es doble:

- **Evitar alucinaciones:** los cálculos y las consultas de datos se resuelven con lógica determinista o con fuentes externas verificables, nunca con el LLM.
- **Ahorrar tokens:** el agente no necesita "razonar" operaciones que se pueden resolver con una llamada a una herramienta tipada; recibe JSON limpio y, opcionalmente, un resumen compacto.

El activo más valioso de PRAXIS no es el número de herramientas, sino que **cada resultado pueda responder de forma fiable a una pregunta**:

> ¿Qué se calculó, con qué datos, con qué versión, con qué fuente, para qué empresa, bajo qué permisos y con qué vigencia?

Si el sistema garantiza esa trazabilidad, tiene mucho más valor empresarial que una colección grande de funciones conectadas a un agente.

## Principios rectores

1. **MCP como interfaz primaria.** PRAXIS expone herramientas vía Model Context Protocol. El LLM y sus tokens los pone y los paga el arnés del cliente (Claude, GPT, Gemini, agentes locales con Ollama). PRAXIS no aloja el "cerebro".
2. **Core determinista y stateless.** `praxis-core` recibe argumentos tipados (Pydantic), ejecuta lógica determinista o consulta APIs externas y devuelve JSON + metadatos. Cero NLP, cero semantic-router, cero plantillas conversacionales.
3. **Multi-tenancy desde el día 1.** Todo dato de empresa está aislado por `company_id` con Row-Level Security de PostgreSQL. El software es self-hosted con licencia MIT; no se comercializa como SaaS en el MVP, pero la arquitectura lo permite.
4. **El código es la fuente de verdad de las herramientas.** La definición canónica vive en el decorador `@tool`; de ahí se generan JSON Schema, OpenAPI, catálogo MCP, documentación y golden tests. La base de datos solo guarda activación, configuración, límites y permisos.
5. **Metadatos obligatorios.** Toda respuesta incluye fuente, momento de consulta, vigencia, unidad, moneda, zona horaria, estimación y errores.
6. **MIT y self-hosted.** Cada instalación usa sus propias claves de APIs externas y cumple sus términos de servicio.

## Para quién

### MVP — tres perfiles de tenant

| Perfil | Cliente | Necesidades dominantes |
|---|---|---|
| `hotel` | Hotel | Agenda y citas, documentos, consultas rápidas (clima, divisas), precios |
| `poligono` | Polígono industrial (uso corporativo y por empresas del polígono) | Datos de empresa, comparativas, documentos, energía |
| `asociacion` | Asociación empresarial / central de compras | Comparación de ofertas y precios, ahorro, documentos, agenda |

### Evolución

Tras consolidar el MVP, PRAXIS se abre a agentes manejados por CEOs de PyMEs y autónomos, y en fases posteriores a todo el C-Level. El modelo `TenantProfile` (catálogo de herramientas por tenant) es la base para futuros planes.

## Las cuatro verticales

PRAXIS es un monorepo con cuatro proyectos individuales.

| Vertical | Responsabilidad | Qué NO hace |
|---|---|---|
| `praxis-core` | Motor de herramientas deterministas + servidor MCP. Recibe argumentos tipados, ejecuta lógica y devuelve JSON + metadatos. Casi stateless. | No hace NLP, ni routing semántico, ni formateo conversacional. |
| `praxis-knowledge` | Base de conocimiento compartido (economía, contabilidad, redacción, marketing, normativa) y base específica por empresa (second-brain del CEO). | No ejecuta cálculos operativos. |
| `praxis-biz` | Capa ligera de conectores + ingesta documental + caché operacional para los datos de la empresa concreta. | No es un ERP maestro. |
| `praxis-sim` | Pipelines/simuladores compuestos versionados que orquestan tools atómicas de `praxis-core` (p. ej. rentabilidad de placas solares). | No duplica lógica de cálculo; la compone. |

La **capa de canal** (WhatsApp/Telegram, semantic-router, formatters) es externa al core y se documenta aparte. No vive dentro de `praxis-core`.

## Mapa mental del MVP

El MVP combina el top-3 real del cliente con un conjunto de herramientas deterministas que demuestran valor sin ser triviales:

- **Documentos:** extracción de facturas (PDF → JSON) y generación de facturas/albaranes.
- **Agenda:** consultar y agendar citas con Google Calendar vía OAuth **por usuario** (agenda personal y de empresa separadas).
- **Comparativas de negocio:** comparación de ofertas y precios y calculadora de ahorro de comisiones TPV. El cálculo de KPIs sobre datos contables llega en v2 con conectores.
- **Calculadoras deterministas:** IVA, márgenes, préstamos, descuentos, fechas, validaciones, unidades, divisas, clima, geocoding.
- **Alertas mínimas:** renovaciones de contratos a 60/30/15 días.

El detalle y los criterios de corte están en [`02-mvp-scope.md`](02-mvp-scope.md). El catálogo completo está en [`03-tools-catalog.md`](03-tools-catalog.md).

## Qué no es PRAXIS

- **No es un ERP.** No es el sistema maestro de contabilidad, facturación ni inventario.
- **No es un chat.** Es una capa de herramientas; la conversación la pone el arnés del agente.
- **No aloja el LLM.** PRAXIS no paga ni ejecuta tokens de modelos de lenguaje.
- **No es un SaaS comercializado** en el MVP, aunque su diseño multi-tenant lo habilita.

## Documentación

El índice completo está en [`docs/`](.). Este fichero es el punto de entrada al marco del proyecto; el alcance está en [`02-mvp-scope.md`](02-mvp-scope.md) y la arquitectura en [`01-architecture.md`](01-architecture.md).
