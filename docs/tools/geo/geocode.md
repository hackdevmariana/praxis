---
estado: MVP
version: 1.0.0
tool: geo.geocode
---

# `geo.geocode` — Geocodificación directa e inversa

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `geo.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true |
| requires_confirmation | false |
| Provider | CartoCiudad (IGN); fallback Nominatim |
| Caché | 7 días |
| Perfiles | `praxis-biz`, `praxis-sim` |

## 2. Semántica exacta

Convierte direcciones en coordenadas (forward) o coordenadas en direcciones (reverse).

- **Modo:** se infiere de los campos. `address` presente → `forward`. `latitude` y `longitude` presentes → `reverse`. Si hay ambos o ninguno → error `invalid_params`.
- `municipality_code` (código INE de 5 dígitos) restringe la búsqueda en forward.
- `limit ∈ [1, 5]`, por defecto `1`.
- **Forward:** devuelve hasta `limit` candidatos ordenados por confianza (mayor primero). Sin resultados → `success: true` con `results: []` y warning `no_results` (no es un error).
- **Reverse:** devuelve la dirección más cercana; si no hay dato → `results: []` y warning `no_results`.
- Coordenadas con 6 decimales (`ROUND_HALF_UP`); `confidence ∈ [0, 1]` con 2 decimales.
- Preferencia por CartoCiudad para direcciones de España. Si falla y responde Nominatim, se añade warning `fallback_source_used` y `source` pasa a `nominatim`.
- La cobertura prioritaria es España; direcciones fuera pueden devolver vacío.
- `municipality_code` no es un parámetro fiable de CartoCiudad: se piden hasta 5 candidatos y se filtra por `ine_code` (`muniCode`) antes de aplicar `limit`.
- CartoCiudad no publica confianza: se deriva de forma determinista (0.98 con `refCatastral`, 0.95 portal, 0.90 callejero, 0.50 resto).

## 3. Contrato Pydantic

```python
from pydantic import BaseModel, Field, model_validator

class GeocodeInput(BaseModel):
    address: str | None = Field(default=None, min_length=3, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    limit: int = Field(default=1, ge=1, le=5)

    @model_validator(mode="after")
    def modo(self):
        forward = self.address is not None
        reverse = self.latitude is not None and self.longitude is not None
        if forward == reverse:
            raise ValueError("Indica 'address' o 'latitude'+'longitude', no ambos")
        return self

class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    normalized_address: str
    ine_code: str | None
    municipality: str | None
    province: str | None
    postal_code: str | None
    confidence: float
    source: str

class GeocodeOutput(BaseModel):
    mode: str  # forward | reverse
    results: list[GeocodeResult]
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Directa | `address="Calle Mayor 1, Madrid"` | 1 resultado, INE 28079, provincia Madrid |
| Directa con límite | `address="Gran Vía, Madrid"`, `limit=5` | hasta 5 resultados |
| Filtro municipal | `address="Calle Mayor 1"`, `municipality_code=28079` | resultado en Madrid |
| Inversa | `lat=40.4155`, `lon=-3.7074` | dirección normalizada de Madrid |
| Sin resultados | `address="zzzzzzzz"` | `results: []`, warning `no_results` |
| Ambos modos | `address` + `latitude` | error `invalid_params` |
| Ningún modo | sin `address` ni coordenadas | error `invalid_params` |
| Latitud inválida | `latitude=95` | error `invalid_params` |
| Código INE inválido | `municipality_code=123` | error `invalid_params` |
| Fallback | CartoCiudad 5xx, Nominatim OK | `source=nominatim`, warning `fallback_source_used` |

## 5. Golden cases

Datos de prueba: stubs inline servidos con `respx` en `tests/test_geo_geocode.py`; no hay fixture `cartociudad-2026-11-13.json` en `tests/fixtures`.

```json
{
  "input": { "address": "Calle Mayor 1, Madrid" },
  "output": {
    "mode": "forward",
    "results": [
      {
        "latitude": 40.415500,
        "longitude": -3.707400,
        "normalized_address": "CALLE MAYOR 1, 28013 MADRID",
        "ine_code": "28079",
        "municipality": "Madrid",
        "province": "Madrid",
        "postal_code": "28013",
        "confidence": 0.98,
        "source": "cartociudad"
      }
    ]
  }
}
```

```json
{
  "input": { "latitude": 40.4155, "longitude": -3.7074 },
  "output": {
    "mode": "reverse",
    "results": [
      {
        "latitude": 40.415500,
        "longitude": -3.707400,
        "normalized_address": "CALLE MAYOR 1, 28013 MADRID",
        "ine_code": "28079",
        "municipality": "Madrid",
        "province": "Madrid",
        "postal_code": "28013",
        "confidence": 0.95,
        "source": "cartociudad"
      }
    ]
  }
}
```

```json
{
  "input": { "address": "zzzzzzzz" },
  "output": { "mode": "forward", "results": [] },
  "metadata": { "warnings": ["no_results"] }
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "cartociudad",
  "source_type": "external_api",
  "source_url": "https://www.cartociudad.es/geocoder/api",
  "retrieved_at": "<now>",
  "valid_until": "<retrieved_at + 7d>",
  "result_type": "geocoding",
  "is_estimated": false,
  "confidence": 0.98,
  "timezone": "Europe/Madrid",
  "attribution": "Geocodificación: CartoCiudad (IGN)",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Alimenta `weather.forecast` a partir de una dirección.
- Usada por `procurement.tpv_savings` para normalizar ubicaciones de locales.
- Base de `geo.route` (v2) con OSRM.

## 8. Decisiones pendientes

- Decidido: añadir `country` y `bounding_box` a la salida en v1.1.
- Pendiente: cobertura fuera de España con Nominatim y cumplimiento de su política de uso; requiere API y validación legal.
- Pendiente: reglas de redistribución de CartoCiudad (no cachear compartido entre tenants); validación legal.
