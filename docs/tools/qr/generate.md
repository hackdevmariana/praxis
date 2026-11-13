---
estado: backlog
version: 0.1.0
tool: qr.generate
---

# `qr.generate` — Generación de códigos QR

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `documents.write` |
| Clasificación | `public` |
| read_only | false |
| idempotent | true (hash del contenido + parámetros) |
| requires_confirmation | false |
| Provider | determinista (generador local) |
| Efectos | crea un `Document` en el VPS |

## 2. Semántica exacta

Codifica texto o una URL en un QR y lo guarda como documento del tenant.

- `content` se codifica tal cual (UTF-8); no se resuelve ni se valida la URL.
- `error_correction ∈ {L, M, Q, H}` (por defecto `M`).
- `format ∈ {png, svg}`; `size_px` aplica a PNG (SVG es escalable).
- `margin_modules ∈ [0, 10]`, por defecto `4`.
- Mismo `content` + parámetros → devuelve el documento existente (`deduplicated=true`).
- El nombre del fichero es un UUID; nunca se usa el contenido como nombre.
- No se permiten tamaños que excedan límites de documento del tenant.

Reglas:

- `content` no vacío y ≤ 2.000 caracteres.
- `size_px ∈ [64, 2000]`.
- `format=png` devuelve `image/png`; `format=svg` devuelve `image/svg+xml`.
- El QR no se envía a terceros ni se registra el contenido en logs.

## 3. Contrato Pydantic

```python
from enum import Enum
from pydantic import BaseModel, Field

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

class QrOutput(BaseModel):
    document_id: str
    path: str
    format: QrFormat
    size_px: int
    mime_type: str
    checksum_sha256: str
    deduplicated: bool
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

## 5. Decisiones pendientes

- Logo central y colores corporativos.
- QR con seguimiento de escaneos (requiere endpoint propio).
- Límites de almacenamiento y caducidad de documentos.
- Promover a spec completa cuando entre en el MVP.
