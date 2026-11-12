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
| Integración | `pytest` + `testcontainers[postgres]` | RLS, PostGIS, pgvector, migraciones |
| Contrato externo | `respx` | APIs externas simuladas |
| Tiempo | `time-machine` | Fechas y zonas horarias |
| API | `Schemathesis` | OpenAPI/MCP schemas |
| UI/manual | — | Escenarios end-to-end del MVP |

## Golden tests por tool

Cada tool incluye, como mínimo:

1. **Caso feliz** con entrada/salida esperada exacta.
2. **Caso límite** (cero, negativos, redondeos, límites de unidad).
3. **Caso de error** (entrada inválida, proveedor caído, permiso insuficiente).

Estructura:

```txt
app/tools/finance/vat/
├── tool.py
├── schemas.py
└── tests/
    ├── test_vat_happy.py
    ├── test_vat_edge.py
    └── test_vat_errors.py
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
- Se prueba el boundary `Decimal → float → Decimal` de `numpy-financial` al céntimo.

## Integración y RLS

Con `testcontainers` (PostgreSQL real):

- Un tenant **nunca** ve filas de otro (deny by default sin `app.company_id`).
- Borrado GDPR por `company_id` elimina todas las filas tenant y anonimiza auditoría.
- Índices y restricciones (`UNIQUE(user_id, company_id)`, `UNIQUE(company_id, number)`).
- PostGIS: búsquedas por proximidad; pgvector: búsqueda híbrida.

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
- `pip-audit` para dependencias.
- Cobertura objetivo: ≥ 90 % en lógica determinista; ≥ 80 % global.

## CI mínimo

```txt
ruff check && ruff format --check
pyright
pytest -q              # unit + properties + respx
pytest -q -m integration   # testcontainers
schemathesis run       # contratos
pip-audit
```
