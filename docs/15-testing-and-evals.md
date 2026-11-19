---
estado: MVP
version: 0.1.0
---

# Testing y evaluaciones

## Pirámide de pruebas

| Nivel | Herramienta | Qué cubre |
|---|---|---|
| Unitario | `pytest` | Lógica determinista de cada tool |
| Propiedades | `Hypothesis` | Casos límite y aleatorios de cálculo |
| Integración | `pytest` + `testcontainers[postgres]` | RLS y migraciones (PostGIS/pgvector: objetivo) |
| Contrato externo | `respx` | APIs externas simuladas |
| Tiempo | `time-machine` | Fechas y zonas horarias |
| API | *(Objetivo)* `Schemathesis` | OpenAPI/MCP schemas; no configurado aún |
| UI/manual | — | Escenarios end-to-end del MVP |

## Golden tests por tool

Cada tool incluye, como mínimo:

1. **Caso feliz** con entrada/salida esperada exacta.
2. **Caso límite** (cero, negativos, redondeos, límites de unidad).
3. **Caso de error** (entrada inválida, proveedor caído, permiso insuficiente).

Estructura:

```txt
app/tools/finance/vat/
├── __init__.py
├── tool.py
└── schemas.py

tests/
├── test_finance_vat.py
├── test_rls_integration.py
└── ...  # suites centralizadas en tests/
```

Los golden tests se generan/validan junto a la definición `@tool` para evitar divergencia entre esquema y prueba.

## Propiedades e invariantes

Con `Hypothesis`:

- `finance.vat`: `base + vat == total` (con redondeo controlado).
- `finance.discounts`: aplicar y revertir recupera el importe original (dentro de tolerancia).
- `finance.loan_schedule`: suma de amortización == principal; último saldo == 0.
- `datetime.business_days`: nunca cuenta festivos; simétrico salvo extremos.
- `units.convert`: convertir ida y vuelta recupera el valor (tolerancia).

Reglas de dinero:

- Todo importe se compara con `Decimal`.
- Los importes se serializan como string en la salida; no se usa `numpy-financial` en el MVP.

## Integración y RLS

Con `testcontainers` (PostgreSQL real):

- Un tenant **nunca** ve filas de otro (deny by default sin contexto `praxis.company_id`).
- Borrado GDPR por `company_id` elimina todas las filas tenant y anonimiza auditoría.
- Índices y restricciones del esquema implementado en migraciones `0001`/`0002`.
- PostGIS (proximidad) y pgvector (búsqueda híbrida): objetivo de fases posteriores.

## APIs externas

- `respx` simula Open-Meteo, BCE y CartoCiudad.
- Se prueban: respuesta correcta, timeout, 429, 5xx, fallback y circuit breaker.
- Nunca se hacen llamadas reales en CI.

## Evaluaciones de selección de tool (v2)

Cuando exista capa de canal/routing:

- **Dataset de frases reales** por perfil de tenant.
- Métricas: accuracy de tool correcta, entidad extraída correcta, tasa de fallback al LLM.
- **Falsos positivos** en tools con efectos = 0 (crear evento/factura sin intención real es crítico).
- Se ejecutan en CI con umbrales mínimos por release.

## Escenarios de aceptación del MVP

Los tres escenarios de [`02-mvp-scope.md`](02-mvp-scope.md#definición-de-hecho-del-mvp) se prueban de extremo a extremo vía MCP:

1. Hotel: consultar agenda + crear cita con confirmación.
2. Polígono/CEO: IVA + extracción de factura + comparación de ofertas.
3. Asociación: ahorro TPV + alerta de renovación.

Cada escenario valida JSON de salida, metadatos completos y registro en `ToolExecutionLog`.

## Calidad de código

- `ruff` para lint/format.
- `pyright` en modo estricto.
- `pip-audit` para dependencias *(pendiente de automatizar)*.
- Cobertura objetivo: ≥ 90 % en lógica determinista; ≥ 80 % global.

## CI mínimo

```txt
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/check_markdown.py
uv run pytest -q --cov=app --cov-report=xml --cov-fail-under=80
uv run coverage report --include="app/tools/finance/*,app/tools/datetime/*,app/tools/units/*,app/tools/validate/*,app/tools/procurement/*,app/money.py,app/business_days.py,app/holidays.py,app/clock.py" --fail-under=90
uv run pytest -q -m integration   # testcontainers
```
