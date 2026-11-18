---
estado: backlog
version: 0.2.0
tool: qr.generate
---

# `qr.generate` — Generación de códigos QR

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `documents.write` (generación) y `documents.read` (estadísticas, v3) |
| Clasificación | `public` |
| read_only | false |
| idempotent | true (hash del contenido + parámetros) |
| requires_confirmation | false |
| Provider | determinista (generador local); servicio de enlaces solo con `track_scans` |
| Efectos | crea un `Document`; con seguimiento, crea un enlace y registra escaneos (v3) |

## 2. Semántica exacta

Codifica texto o una URL en un QR y lo guarda como documento del tenant.

- `content` se codifica tal cual (UTF-8); no se resuelve ni se valida la URL.
- `error_correction ∈ {L, M, Q, H}` (por defecto `M`).
- `format ∈ {png, svg}`; `size_px` aplica a PNG (SVG es escalable).
- `margin_modules ∈ [0, 10]`, por defecto `4`.
- `track_scans` (por defecto `false`): si es `true`, `content` debe ser una URL absoluta `http(s)` y el QR codifica el enlace de seguimiento del tenant (`https://qr.praxis.example/r/{slug}`), no la URL final.
- `expires_at` (opcional, solo con seguimiento): fecha ISO 8601 futura; a partir de ella el enlace redirige a `404`.
- Mismo `content` + parámetros → devuelve el documento existente (`deduplicated=true`).
- El nombre del fichero es un UUID; nunca se usa el contenido como nombre.
- No se permiten tamaños que excedan límites de documento del tenant.

Reglas:

- `content` no vacío y ≤ 2.000 caracteres.
- `size_px ∈ [64, 2000]`.
- `format=png` devuelve `image/png`; `format=svg` devuelve `image/svg+xml`.
- `track_scans=true` exige URL absoluta `http(s)`; se rechazan `javascript:`, `data:` y rutas relativas.
- Con `track_scans=false` el QR es estático y no requiere ningún endpoint.
- El QR no se envía a terceros ni se registra el contenido en logs.

## 3. Contrato Pydantic

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class QrFormat(str, Enum):
    png = "png"
    svg = "svg"

class QrErrorCorrection(str, Enum):
    L = "L"
    M = "M"
    Q = "Q"
    H = "H"

class QrInput(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    size_px: int = Field(default=512, ge=64, le=2000)
    error_correction: QrErrorCorrection = QrErrorCorrection.M
    format: QrFormat = QrFormat.png
    margin_modules: int = Field(default=4, ge=0, le=10)
    track_scans: bool = False
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def tracking(self):
        if self.expires_at is not None and not self.track_scans:
            raise ValueError("expires_at requiere track_scans=true")
        if self.track_scans and not self.content.startswith(("http://", "https://")):
            raise ValueError("track_scans requiere una URL http(s)")
        return self

class QrOutput(BaseModel):
    document_id: str
    path: str
    format: QrFormat
    size_px: int
    mime_type: str
    checksum_sha256: str
    deduplicated: bool
    tracking_url: str | None
    slug: str | None
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| URL simple | `https://praxis.example/t/abc` | PNG 512 px, `image/png` |
| SVG | `format=svg` | `image/svg+xml` |
| Alta corrección | `error_correction=H` | QR con más redundancia |
| Contenido vacío | `content=""` | error `invalid_params` |
| Tamaño fuera de rango | `size_px=32` | error `invalid_params` |
| Repetición | mismo contenido y parámetros | `deduplicated=true` |
| Texto largo | 2.001 caracteres | error `invalid_params` |
| QR con seguimiento | `track_scans=true`, URL `https` | QR apunta a `/r/{slug}` |
| Seguimiento sin URL | `track_scans=true`, `content="hola"` | error `invalid_params` |
| Caducidad sin seguimiento | `expires_at` con `track_scans=false` | error `invalid_params` |
| Caducidad pasada | `expires_at` anterior a hoy | error `invalid_params` |
| Enlace caducado | `GET /r/{slug}` tras `expires_at` | `404`, sin redirección |
| Servicio caído | enlaces no disponibles | error `provider_unavailable` |
| Stats sin API key | `GET /api/v1/qr/links/{slug}/stats` | error `permission_denied` |

## 5. Seguimiento de escaneos (v3)

El seguimiento requiere un servicio HTTP propio, fuera del núcleo determinista; **no entra en el MVP**.

**Flujo**

1. `qr.generate(track_scans=true, content="https://destino.example")` genera un slug aleatorio base62 de 8 caracteres y guarda `{slug, company_id, target_url, expires_at}`.
2. El QR codifica `https://qr.praxis.example/r/{slug}`.
3. `GET /r/{slug}` responde `302` al destino y registra el escaneo.
4. `GET /api/v1/qr/links/{slug}/stats` devuelve las métricas del tenant.

**Endpoint de redirección**

- `GET /r/{slug}`: `302`, `Cache-Control: no-store`, `X-Robots-Tag: noindex`, sin cookies.
- Slug inexistente o caducado → `404`; el destino siempre se lee del almacén, nunca de la URL (sin open redirect).
- Límites: 60 req/min por IP y 1.000 req/min por tenant.
- Registro por escaneo: `scanned_at`, `slug`, `company_id`, `user_agent` y `referer` truncados, e IP **hasheada con sal rotativa**. Retención 90 días; sin PII en claro.
- El alta no sigue redirecciones del destino: se guarda la URL tal cual se validó.

**Estadísticas**

- `scans_total`, `scans_last_7d`, `unique_ips_approx` (sobre el hash) y `by_day`.
- RLS por `company_id`; el slug es opaco pero no autoriza por sí solo: las stats exigen API key del tenant.

**Reglas**

- `expires_at` debe ser futura y solo es válida con `track_scans=true`.
- Si el servicio de enlaces no está disponible, `qr.generate` falla con `provider_unavailable`; no se devuelve un QR sin seguimiento de forma silenciosa.
- La idempotencia incluye `content`, `track_scans` y `expires_at`: la misma alta devuelve el mismo slug.
- Un mismo destino con distintos parámetros de campaña produce enlaces distintos; múltiples enlaces sin cambiar la URL quedan para una revisión futura (`idempotency_key`).

## 6. Decisiones pendientes

- Pendiente: logo central y colores corporativos; decisión de producto.
- Pendiente: dominio del servicio de enlaces (`qr.praxis.example` frente a dominio del tenant) y certificado; requiere infraestructura.
- Pendiente: enlaces editables (cambiar el destino sin regenerar el QR); decisión de producto.
- Pendiente: múltiples enlaces al mismo destino mediante `idempotency_key`; decisión de producto.
- Pendiente: agregación y exportación de estadísticas; retención definitiva; validación legal.
- Pendiente: límites de almacenamiento y caducidad de documentos; validación legal.
- Pendiente: promover a spec completa cuando entre en el MVP.
