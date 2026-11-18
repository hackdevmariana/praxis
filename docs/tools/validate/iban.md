---
estado: MVP
version: 1.0.0
tool: validate.iban
---

# `validate.iban` — Validación de IBAN y BIC

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
| Datos en log | **No** se registra el IBAN en claro; solo `input_hash` |

## 2. Semántica exacta

Valida la estructura de un IBAN y, opcionalmente, un BIC/SWIFT. **No verifica** que la cuenta exista ni esté operativa.

1. **Normalización:** eliminar espacios y pasar a mayúsculas.
2. **Longitud por país:** cada país tiene longitud fija de IBAN (p. ej. ES = 24).
3. **Estructura BBAN:** validación del formato por país según `python-stdnum`.
4. **Dígitos de control:** mover los 4 primeros caracteres al final, convertir letras a números (`A=10`…`Z=35`) y comprobar `mod 97 == 1`.
5. **Dígito de control nacional:** en IBAN españoles se valida además el CCC (`stdnum.es.iban` / `stdnum.es.ccc`); un CCC inválido produce `reason=invalid_checksum`.
6. **BIC (opcional):** si se aporta, validar formato de 8 u 11 caracteres y coherencia básica con el país del IBAN.

Reglas:

- Validación **offline**; no consulta la entidad bancaria ni el VIES.
- `bban` devuelve la parte nacional (sin código de país ni dígitos de control); es `null` cuando `valid=false`.
- `bic_valid` es `null` si no se aporta BIC. Un BIC con formato inválido **no** invalida el IBAN.
- La coherencia de país del BIC solo se evalúa si el IBAN es válido; si el IBAN falla, se devuelve su `reason` y `bic_valid` refleja únicamente el formato del BIC.
- `reason` usa códigos estables: `invalid_length`, `invalid_format`, `invalid_checksum`, `unknown_country`, `bic_country_mismatch`.

## 3. Contrato Pydantic

```python
from pydantic import BaseModel, Field

class IbanInput(BaseModel):
    iban: str = Field(min_length=4, max_length=42)
    bic: str | None = Field(default=None, max_length=11)

class IbanOutput(BaseModel):
    valid: bool
    normalized: str
    country: str | None = None
    bban: str | None = None
    bic_valid: bool | None = None
    reason: str | None = None
    warning: str | None = "Un IBAN válido no implica que la cuenta exista o esté operativa."
```

## 4. Matriz de casos

| Caso | `iban` | `bic` | `valid` | Notas |
|---|---|---|---|---|
| IBAN ES válido | `ES9121000418450200051332` | — | true | `country=ES` |
| IBAN con espacios | `ES91 2100 0418 4502 0005 1332` | — | true | `normalized` sin espacios |
| IBAN minúsculas | `es9121000418450200051332` | — | true | |
| Checksum IBAN erróneo | `ES9121000418450200051333` | — | false | `invalid_checksum` |
| CCC español inválido (mod-97 válido) | `ES6421000418450200051333` | — | false | `invalid_checksum` |
| Longitud incorrecta | `ES912100041845020005133` | — | false | `invalid_length` |
| País desconocido | `ZZ9121000418450200051332` | — | false | `unknown_country` |
| BIC válido (8) | `ES9121000418450200051332` | `CAIXESBB` | true | `bic_valid=true` |
| BIC válido (11) | `ES9121000418450200051332` | `CAIXESBBXXX` | true | `bic_valid=true` |
| BIC inválido | `ES9121000418450200051332` | `CAIX1SBB` | true | `bic_valid=false` |
| IBAN y BIC de países distintos | `ES9121000418450200051332` | `BNPAFRPPXXX` | false | `bic_country_mismatch` |

## 5. Golden cases

```json
{
  "input": { "iban": "ES9121000418450200051332" },
  "output": {
    "valid": true,
    "normalized": "ES9121000418450200051332",
    "country": "ES",
    "bban": "21000418450200051332",
    "bic_valid": null,
    "reason": null,
    "warning": "Un IBAN válido no implica que la cuenta exista o esté operativa."
  }
}
```

```json
{
  "input": { "iban": "es91 2100 0418 4502 0005 1332", "bic": "CAIXESBBXXX" },
  "output": {
    "valid": true,
    "normalized": "ES9121000418450200051332",
    "country": "ES",
    "bban": "21000418450200051332",
    "bic_valid": true,
    "reason": null,
    "warning": "Un IBAN válido no implica que la cuenta exista o esté operativa."
  }
}
```

```json
{
  "input": { "iban": "ES9121000418450200051333" },
  "output": {
    "valid": false,
    "normalized": "ES9121000418450200051333",
    "country": "ES",
    "bban": null,
    "bic_valid": null,
    "reason": "invalid_checksum",
    "warning": "Un IBAN válido no implica que la cuenta exista o esté operativa."
  }
}
```

```json
{
  "input": { "iban": "ES6421000418450200051333" },
  "output": {
    "valid": false,
    "normalized": "ES6421000418450200051333",
    "country": "ES",
    "bban": null,
    "bic_valid": null,
    "reason": "invalid_checksum",
    "warning": "Un IBAN válido no implica que la cuenta exista o esté operativa."
  }
}
```

```json
{
  "input": { "iban": "ES912100041845020005133", "bic": "CAIX1SBB" },
  "output": {
    "valid": false,
    "normalized": "ES912100041845020005133",
    "country": "ES",
    "bban": null,
    "bic_valid": false,
    "reason": "invalid_length",
    "warning": "Un IBAN válido no implica que la cuenta exista o esté operativa."
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

- Usada por `documents.extract_invoice` para validar datos de pago.
- Base para `finance.cashflow_13w` (v2) al cruzar cobros/pagos con cuentas.

## 8. Decisiones pendientes

- Implementado: en v1.0, además del mod-97 se valida el dígito de control nacional español (CCC) vía `stdnum.es.iban`.
- Decidido: documentar los límites de cobertura de `python-stdnum` para IBAN de países no europeos.
- Implementado: códigos `reason` estables (`invalid_length`, `invalid_format`, `invalid_checksum`, `unknown_country`, `bic_country_mismatch`).
