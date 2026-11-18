---
estado: MVP
version: 1.0.0
tool: units.convert
---

# `units.convert` — Conversión de unidades

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `units.convert` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (`pint`) |
| Caché | n/a |
| Perfiles | all |

## 2. Semántica exacta

Convierte un valor entre unidades compatibles usando `pint`.

1. **Parseo:** interpreta `from_unit` y `to_unit` con el registro de `pint` (símbolos y nombres: `km`, `mile`, `kg`, `lb`, `L`, `gal`, `m²`, `ft²`, `°C`, `°F`, `kWh`, `MJ`…).
2. **Compatibilidad:** si las dimensiones no coinciden → error `incompatible_units`.
3. **Conversión:** `resultado = value × factor`, con soporte de unidades con offset (temperatura).
4. **Redondeo:** cuantizar a `precision` decimales (por defecto 6, máximo 12) con `ROUND_HALF_UP`.
5. **Unidad canónica:** devolver la unidad normalizada por `pint` (p. ej. `meter`, `kilogram`).

Reglas:

- Se aceptan valores negativos y cero.
- **Temperatura:** se tratan como magnitudes absolutas, no como diferencias. `0 °C = 32 °F`. Para diferencias de temperatura debe usarse otra tool (backlog `units.convert_delta`).
- **Precisión:** `pint` opera internamente en `float`; el resultado se cuantiza a `precision` decimales, así que no se garantiza exactitud más allá de esa precisión.
- No se convierten magnitudes monetarias (usar `currency.convert`). Una unidad monetaria desconocida produce `invalid_params`.

## 3. Contrato Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class UnitsConvertInput(BaseModel):
    value: Decimal
    from_unit: str = Field(min_length=1, max_length=32)
    to_unit: str = Field(min_length=1, max_length=32)
    precision: int = Field(default=6, ge=0, le=12)

class UnitsConvertOutput(BaseModel):
    value: Decimal          # serializado como string
    from_unit: str          # unidad canónica
    to_unit: str            # unidad canónica
    dimension: str          # dimensionalidad pint; p. ej. "[length]" o "[mass] * [length] ** 2 / [time] ** 2"
    factor: Decimal         # factor de conversión aplicado (sin offset)
```

## 4. Matriz de casos

Salvo indicación, `precision=6` y el valor se muestra ya cuantizado.

| Caso | Entrada | Resultado |
|---|---|---|
| Longitud | `10 km → mile` | `6.213712` mile |
| Longitud inversa | `1 mile → km` | `1.609344` km |
| Masa | `2 kg → lb` | `4.409245` lb |
| Volumen | `1 L → gal (US)` | `0.264172` gal |
| Superficie | `100 m² → ft²` | `1076.391042` ft² |
| Energía | `1 kWh → MJ` | `3.600000` MJ |
| Temperatura | `0 °C → °F` (`precision=2`) | `32.00` °F |
| Temperatura | `100 °C → °F` (`precision=2`) | `212.00` °F |
| Cero | `0 km → m` | `0.000000` m |
| Negativo | `-5 °C → °F` (`precision=2`) | `23.00` °F |
| Dimensiones incompatibles | `1 kg → km` | error `incompatible_units` |
| Unidad desconocida | `1 foo → m` | error `invalid_params` |
| Precisión 0 | `1.234 km → m` | `1234` m |
| Precisión 12 | `1 in → m` | `0.025400000000` m |

## 5. Golden cases

```json
{
  "input": { "value": "10", "from_unit": "km", "to_unit": "mile", "precision": 6 },
  "output": {
    "value": "6.213712",
    "from_unit": "kilometer",
    "to_unit": "mile",
    "dimension": "[length]",
    "factor": "0.621371192237334"
  }
}
```

```json
{
  "input": { "value": "0", "from_unit": "°C", "to_unit": "°F", "precision": 2 },
  "output": {
    "value": "32.00",
    "from_unit": "degree_Celsius",
    "to_unit": "degree_Fahrenheit",
    "dimension": "[temperature]",
    "factor": "1.8"
  }
}
```

```json
{
  "input": { "value": "100", "from_unit": "°C", "to_unit": "°F", "precision": 2 },
  "output": {
    "value": "212.00",
    "from_unit": "degree_Celsius",
    "to_unit": "degree_Fahrenheit",
    "dimension": "[temperature]",
    "factor": "1.8"
  }
}
```

```json
{
  "input": { "value": "1", "from_unit": "kWh", "to_unit": "MJ", "precision": 6 },
  "output": {
    "value": "3.600000",
    "from_unit": "kilowatt_hour",
    "to_unit": "megajoule",
    "dimension": "[mass] * [length] ** 2 / [time] ** 2",
    "factor": "3.6"
  }
}
```

```json
{
  "input": { "value": "1", "from_unit": "kg", "to_unit": "km", "precision": 6 },
  "error": { "code": "incompatible_units", "message": "No se puede convertir [mass] a [length]" }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "calculation",
  "is_estimated": false,
  "confidence": null,
  "unit_system": "metric",
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": false
}
```

Notas:

- `factor` en unidades con offset (temperatura) refleja solo el factor multiplicativo; el offset se aplica al `value`.
- Si el usuario pide una salida en unidades ambiguas (`gal` UK vs US), `pint` exige sufijo (`gal` = US en el registro por defecto); documentar en la descripción MCP.

## 7. Composiciones

- Usada por `energy.*` (v2) para normalizar consumos (`kWh`, `MWh`, `MJ`).
- Usada por `sim.solar_payback` para superficies (`m²`, `ft²`) y energía.
- Usada por herramientas de logística y superficies de polígonos industriales.

## 8. Decisiones pendientes

- Decidido: `units.convert_delta` para diferencias de temperatura en backlog.
- Implementado: `precision` por defecto 6 (máximo 12) para no perder exactitud en conversiones pequeñas.
- Implementado: las unidades ambiguas se resuelven con el registro de `pint` (`gal` = US) y se documentan en `mcp_description`.
