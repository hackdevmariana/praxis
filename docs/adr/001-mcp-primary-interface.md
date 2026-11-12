# ADR-001: MCP como interfaz primaria

- **Estado:** aceptado
- **Fecha:** 2026-11-12

## Contexto

PRAXIS debe ser independiente del agente que lo consume. Los clientes usan distintos LLMs (Claude, GPT, Gemini, agentes locales) y no quieren configurar integraciones específicas. La API REST no resuelve el descubrimiento de herramientas ni la descripción para el agente.

## Decisión

La interfaz primaria de PRAXIS es el **Model Context Protocol**. El servidor MCP expone herramientas tipadas con esquemas generados desde Pydantic. La API REST queda reducida a operaciones auxiliares (`/health`, administración).

El LLM y sus tokens los aporta el arnés del cliente; PRAXIS no aloja el cerebro.

## Consecuencias

- Cualquier agente compatible puede usar PRAXIS sin configuración específica.
- Las descripciones y esquemas deben diseñarse para selección por parte del agente.
- Se necesita versionado cuidadoso del contrato MCP y deprecación (ADR relacionado: 17-versioning).
- La capa de canal (WhatsApp/Telegram) es externa y puede invocar el mismo core o el MCP.
