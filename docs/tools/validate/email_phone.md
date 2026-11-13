---
estado: MVP
version: 1.0.0
tool: validate.email_phone
---

# `validate.email_phone` — Validación de email y teléfono

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `validation.check` |
| Clasificación | `personal` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | determinista (`email-validator`, `phonenumbers`) |
| Caché | n/a |
| Perfiles | all |
| Datos en log | **No** se registra el contacto en claro; solo `input_hash` |

## 2. Semántica exacta

Valida **formato** de email y teléfono. No verifica que el buzón exista ni la titularidad del número.

- **Email (`email-validator`):**
  - Valida sintaxis, longitud y dominio (IDN normalizado).
  - **No** hace comprobación de entregabilidad ni consultas DNS en el MVP.
  - Normaliza el dominio a minúsculas; conserva la parte local.
- **Teléfono (`phonenumbers`):**
  - Parseo con región por defecto `ES` (`default_region`).
  - `is_valid_number` y clasificación (`mobile`, `fixed_line`, `voip`, `toll_free`, `unknown`).
  - Salida en **E.164** y formato internacional legible.
- Al menos uno de los dos campos debe estar presente (`model_validator`).

## 3. Contrato Pydantic

```python
from pydantic import BaseModel, Field, model_validator

class EmailPhoneInput(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    default_region: str = Field(default="ES", min_length=2, max_length=2)

    @model_validator(mode="after")
    def al_menos_uno(self):
        if not self.email and not self.phone:
            raise ValueError("Indica al menos email o phone")
        return self

class EmailPhoneOutput(BaseModel):
    email_valid: bool | None = None
    email_normalized: str | None = None
    email_reason: str | None = None
    phone_valid: bool | None = None
    phone_e164: str | None = None
    phone_international: str | None = None
    phone_type: str | None = None
    phone_country: str | None = None
    phone_reason: str | None = None
```

## 4. Matriz de casos

| Caso | `email` | `phone` | Resultado |
|---|---|---|---|
| Ambos válidos | `ceo@empresa.es` | `+34 612 345 678` | email_valid=true, phone_valid=true, phone_type=mobile |
| Email válido, teléfono ausente | `a@b.es` | — | email_valid=true, phone_valid=null |
| Email sin dominio | `usuario@` | — | email_valid=false, `invalid_format` |
| Email con espacios | ` usuario@empresa.es ` | — | email_valid=true, normalizado |
| Teléfono fijo ES | — | `915 55 55 55` | phone_valid=true, phone_type=fixed_line |
| Teléfono internacional | — | `+33 1 42 68 53 00` | phone_valid=true, phone_country=FR |
| Teléfono demasiado corto | — | `123` | phone_valid=false, `invalid_length` |
| Ningún campo | — | — | error `invalid_params` |

## 5. Golden cases

```json
{
  "input": { "email": "ceo@empresa.es", "phone": "+34 612 345 678" },
  "output": {
    "email_valid": true,
    "email_normalized": "ceo@empresa.es",
    "email_reason": null,
    "phone_valid": true,
    "phone_e164": "+34612345678",
    "phone_international": "+34 612 34 56 78",
    "phone_type": "mobile",
    "phone_country": "ES",
    "phone_reason": null
  }
}
```

```json
{
  "input": { "email": "usuario@" },
  "output": {
    "email_valid": false,
    "email_normalized": null,
    "email_reason": "invalid_format",
    "phone_valid": null
  }
}
```

```json
{
  "input": { "phone": "915 55 55 55", "default_region": "ES" },
  "output": {
    "email_valid": null,
    "phone_valid": true,
    "phone_e164": "+34915555555",
    "phone_international": "+34 915 55 55 55",
    "phone_type": "fixed_line",
    "phone_country": "ES",
    "phone_reason": null
  }
}
```

```json
{
  "input": { "phone": "+33 1 42 68 53 00", "default_region": "ES" },
  "output": {
    "email_valid": null,
    "phone_valid": true,
    "phone_e164": "+33142685300",
    "phone_type": "fixed_line",
    "phone_country": "FR",
    "phone_reason": null
  }
}
```

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
  "timezone": "Europe/Madrid",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Usada por `calendar.create_event` para validar emails de asistentes.
- Usada por conectores de notificación (WhatsApp/email) para validar destinatarios.
- Base para `alerts.contract_renewal` al elegir canal y contacto.

## 8. Decisiones pendientes

- ¿Añadir comprobación DNS/MX opcional (`check_dns`) en v2? Implicaría red y no determinismo; propuesta: tool separada.
- ¿Devolver `phone_type` como enum cerrado o texto? Propuesta: enum estable.
- Códigos `reason` estables: `invalid_format`, `invalid_length`, `invalid_country`, `parse_error`.
