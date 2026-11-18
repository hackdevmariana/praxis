---
estado: backlog
version: 0.1.0
tool: audit.web_basic
---

# `audit.web_basic` — Auditoría web básica

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `audit.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | HTTP directo (cliente propio endurecido) |
| Caché | 24 h por URL |

## 2. Semántica exacta

Comprueba HTTPS, TLS, cabeceras de seguridad y respuesta HTTP de una URL pública.

- Solo `http`/`https`, puertos `80`/`443`; se rechazan credenciales embebidas en la URL.
- **Anti-SSRF:** resolución DNS previa y rechazo de IP privadas, loopback, link-local, multicast, reservadas y metadatos cloud; los redirects (máx. 5) se revalidan con las mismas reglas.
- No se envían cookies ni credenciales; cuerpo máximo leído 256 KB y solo para cabeceras/estado.
- Cabeceras evaluadas y peso en el score: `strict-transport-security` 10, `content-security-policy` 10, `x-content-type-options` 5, `x-frame-options` 5, `referrer-policy` 5, `permissions-policy` 5. Score = 100 − penalizaciones.
- TLS inválido o caducado → issue `high` y score máximo 50.
- `server` expuesto → −5. Estado no 2xx/3xx → issue `medium` (−10).
- `checked_at` y `expires_at` TLS en ISO 8601.

Reglas:

- `timeout_ms ∈ [1000, 15000]`, por defecto `5000`.
- La respuesta incluye `issues` ordenados por severidad; una cabecera ausente genera un issue.
- El resultado es una foto puntual, no un escaneo de vulnerabilidades.

## 3. Contrato Pydantic

```python
from datetime import datetime
from pydantic import BaseModel, Field

class AuditInput(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    timeout_ms: int = Field(default=5000, ge=1000, le=15000)
    check_tls: bool = True

class HeaderCheck(BaseModel):
    present: bool
    value: str | None

class TlsInfo(BaseModel):
    enabled: bool
    valid: bool | None
    issuer: str | None
    expires_at: datetime | None
    days_remaining: int | None

class AuditIssue(BaseModel):
    severity: str  # low | medium | high
    code: str
    message: str

class AuditOutput(BaseModel):
    requested_url: str
    final_url: str
    status_code: int
    response_time_ms: int
    redirect_count: int
    tls: TlsInfo
    security_headers: dict[str, HeaderCheck]
    issues: list[AuditIssue]
    score: int
    checked_at: datetime
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Caso base | `https://example.com` | 200, TLS válido, score 70 |
| URL privada | `http://127.0.0.1` | error `invalid_params` (SSRF) |
| Metadatos cloud | `http://169.254.169.254` | rechazado |
| Sin HTTPS | `http://example.com` | issue `high` (`no_https`) |
| TLS caducado | certificado vencido | `tls.valid=false`, score ≤ 50 |
| Redirect externo a IP privada | 302 → `10.0.0.5` | rechazado |
| Timeout | servidor lento | error `provider_unavailable` |
| Demasiados redirects | > 5 | issue `high` |

## 5. Decisiones pendientes

- Pendiente: comprobación de cookies (`Secure`, `HttpOnly`, `SameSite`); decisión de producto.
- Pendiente: puertos alternativos y entornos de staging; decisión de producto.
- Pendiente: integración con Lighthouse/axe para rendimiento y accesibilidad; requiere API.
- Pendiente: alertas periódicas de cambios en cabeceras; decidir canal y periodicidad.
- Pendiente: promover a spec completa cuando entre en el MVP.
