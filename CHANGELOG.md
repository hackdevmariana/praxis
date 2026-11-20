# Changelog

Todas las entradas notables se documentarán en este archivo. Formato: Keep a Changelog. Versión: SemVer.

## [Unreleased]

### Added

- 21 tools del MVP expuestas por REST y MCP.
- `/health`, autenticación JWT/API key, toolsets por tenant, idempotencia y auditoría.
- Stores SQLAlchemy con RLS, migraciones Alembic y seeder demo.
- Documentación base, 42 specs de tools, índices, CI y comprobador de Markdown.
- 4 tools v2 de finanzas determinista: `finance.business_kpi`, `finance.ebitda`, `finance.break_even` y `finance.cashflow_13w`.
- Adaptadores reales configurables para Google Calendar OAuth, OCR Tesseract, WeasyPrint, almacenamiento local, persistencia SQL de eventos/contratos/avisos y notificación SMTP.
- 4 tools v2 de compras: `procurement.detect_price_increase`, `procurement.savings_ledger`, `procurement.renewal_calendar` y `procurement.rfp_generation`.
- Migración `0004_procurement_v2` con `savings_entries` y RLS; repositorios SQL de ahorros y renovaciones y `ArtifactStore.save_artifact`.
- 3 tools v2 de energía determinista: `energy.carbon_footprint`, `energy.tariff_simulator` y `energy.self_consumption_payback`.

### Changed

### Deprecated

### Removed

### Fixed

### Security
