---
estado: MVP
version: 1.0.0
tool: validate.spanish_id
---

# `validate.spanish_id` — Validación de NIF, NIE y CIF

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `validation.check` |
| Clasificación | `personal` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (`python-stdnum`) |
| Caché | n/a |
| Perfiles | all |
| Datos en log | **No** se registra el identificador en claro; solo `input_hash` |

## 2. Semántica exacta

Valida identificadores fiscales españoles. Un **checksum válido no prueba** que la empresa o persona exista ni esté activa.

1. **Normalización:** eliminar espacios, guiones y puntos; pasar a mayúsculas.
2. **Detección de tipo** (`type=auto`):
   - `NIF` (DNI): 8 dígitos + letra de control.
   - `NIE`: `X`/`Y`/`Z` + 7 dígitos + letra de control.
   - `CIF`: letra de tipo + 7 dígitos + control (dígito o letra).
3. **NIF/NIE:** letra de control = `"TRWAGMYFPDXBNJZSQVHLCKE"[n % 23]`, donde para NIE se sustituye `X=0`, `Y=1`, `Z=2` antes del módulo.
4. **CIF:** control calculado con el algoritmo de `python-stdnum`; se acepta el carácter de control esperado (dígito o letra según el tipo de entidad).
5. **Tipo explícito:** si `type` no es `auto` y el valor no encaja, `valid=false` con `reason=type_mismatch`.

Reglas:

- La validación es **offline**; no consulta VIES ni registros.
- `normalized` devuelve la forma canónica sin separadores.
- `checksum_ok` distingue el fallo de formato del fallo de dígito de control: es `false` cuando el formato no encaja y, cuando encaja, refleja el checksum (coincide con `valid`).
- `reason` usa códigos estables: `invalid_length`, `invalid_format`, `invalid_checksum`, `type_mismatch`.

## 3. Contrato Pydantic

```python
from enum import Enum
from pydantic import BaseModel, Field

class IdType(str, Enum):
    auto = "auto"
    nif = "nif"
    nie = "nie"
    cif = "cif"

class SpanishIdInput(BaseModel):
    value: str = Field(min_length=1, max_length=20)
    type: IdType = IdType.auto

class SpanishIdOutput(BaseModel):
    valid: bool
    id_type: IdType
    normalized: str
    checksum_ok: bool
    reason: str | None = None
    warning: str | None = "Un identificador válido no implica que la empresa o persona exista o esté activa."
```

## 4. Matriz de casos

| Caso | `value` | `type` | `valid` | `id_type` | `checksum_ok` | `reason` |
|---|---|---|---|---|---|---|
| DNI válido | `12345678Z` | auto | true | nif | true | null |
| DNI con separadores | `12.345.678-Z` | auto | true | nif | true | null |
| DNI minúsculas | `12345678z` | auto | true | nif | true | null |
| DNI checksum erróneo | `12345678A` | auto | false | nif | false | `invalid_checksum` |
| NIE válido | `X1234567L` | auto | true | nie | true | null |
| CIF válido | `A58818501` | auto | true | cif | true | null |
| CIF checksum erróneo | `A58818500` | auto | false | cif | false | `invalid_checksum` |
| Longitud incorrecta | `1234` | auto | false | nif | false | `invalid_length` |
| Tipo forzado incompatible | `X1234567L` | nif | false | nif | false | `type_mismatch` |
| Vacío | `` | auto | error `invalid_params` | — | — | — |

## 5. Golden cases

```json
{
  "input": { "value": "12345678Z", "type": "auto" },
  "output": {
    "valid": true,
    "id_type": "nif",
    "normalized": "12345678Z",
    "checksum_ok": true,
    "reason": null,
    "warning": "Un identificador válido no implica que la empresa o persona exista o esté activa."
  }
}
```

```json
{
  "input": { "value": "12.345.678-z", "type": "auto" },
  "output": {
    "valid": true,
    "id_type": "nif",
    "normalized": "12345678Z",
    "checksum_ok": true,
    "reason": null,
    "warning": "Un identificador válido no implica que la empresa o persona exista o esté activa."
  }
}
```

```json
{
  "input": { "value": "X1234567L", "type": "auto" },
  "output": {
    "valid": true,
    "id_type": "nie",
    "normalized": "X1234567L",
    "checksum_ok": true,
    "reason": null,
    "warning": "Un identificador válido no implica que la empresa o persona exista o esté activa."
  }
}
```

```json
{
  "input": { "value": "A58818500", "type": "auto" },
  "output": {
    "valid": false,
    "id_type": "cif",
    "normalized": "A58818500",
    "checksum_ok": false,
    "reason": "invalid_checksum",
    "warning": "Un identificador válido no implica que la empresa o persona exista o esté activa."
  }
}
```

```json
{
  "input": { "value": "1234", "type": "auto" },
  "output": {
    "valid": false,
    "id_type": "nif",
    "normalized": "1234",
    "checksum_ok": false,
    "reason": "invalid_length",
    "warning": "Un identificador válido no implica que la empresa o persona exista o esté activa."
  }
}
```

Los campos omitidos en un golden toman el valor por defecto del contrato (`null`).

## 6. Metadatos de respuesta

```json
{
  "source": "deterministic",
  "source_type": "deterministic",
  "retrieved_at": "<now>",
  "valid_until": null,
  "result_type": "validation",
  "is_estimated": false,
  "confidence": null,
  "unit_system": "metric",
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": [],
  "legal_disclaimer_required": false
}
```

## 7. Composiciones

- Usada por `documents.extract_invoice` para validar el CIF del emisor.
- Usada por `procurement.compare_offers` para normalizar proveedores (v2).
- Base de `legal.company_risk` (backlog) para cruzar con fuentes registrales.

## 8. Decisiones pendientes

- Implementado: validación de NIE en v1.
- Pendiente: validar número de Seguridad Social; decisión de producto.
- Decidido: consulta VIES en v2 como tool separada `validate.vies_eu`.
- Pendiente: implementación de `validate.vies_eu`; requiere API externa.
- Implementado: `reason` usa códigos estables (`invalid_length`, `invalid_format`, `invalid_checksum`, `type_mismatch`).
