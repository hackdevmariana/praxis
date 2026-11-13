---
estado: MVP
version: 1.0.0
tool: weather.forecast
---

# `weather.forecast` — Previsión meteorológica

## 1. Metadatos

| Campo | Valor |
|---|---|
| Permisos | `weather.read` |
| Clasificación | `public` |
| read_only | true |
| idempotent | true (dentro de la ventana de caché) |
| requires_confirmation | false |
| Provider | Open-Meteo (fallback AEMET en v2) |
| Caché | 30 min (previsión) |
| Perfiles | `praxis-sim`, `praxis-biz` |

## 2. Semántica exacta

Previsión meteorológica por coordenadas para los próximos 1–7 días.

- `granularity=daily` (por defecto): un punto por día con agregados.
- `granularity=hourly`: un punto por hora (24 × `days`), en la zona `timezone`.
- `timezone` se envía a Open-Meteo; por defecto `Europe/Madrid`. Los `time` de salida son ISO 8601 locales (sin offset) para `daily`, y con offset para `hourly`.
- `variables` es un subconjunto de las soportadas; si se omite, se usan las de por defecto.
- Unidades siempre métricas: °C, mm, km/h, %, W/m², índice UV (0–11+). Se declaran en `metadata.units`.

Variables y sus agregados diarios:

| Variable canónica | Diario |
|---|---|
| `temperature_2m` | `temperature_2m_max`, `temperature_2m_min` |
| `apparent_temperature` | `apparent_temperature_max` |
| `precipitation_probability` | `precipitation_probability_max` |
| `precipitation` | `precipitation_sum` |
| `wind_speed_10m` | `wind_speed_10m_max` |
| `relative_humidity_2m` | `relative_humidity_2m_mean` |
| `shortwave_radiation` | `shortwave_radiation_sum` |
| `cloud_cover` | `cloud_cover_mean` |
| `uv_index` | `uv_index_max` |

Reglas:

- `latitude ∈ [−90, 90]`, `longitude ∈ [−180, 180]`; si se invierten, error `invalid_params`.
- `days ∈ [1, 7]`.
- Si el proveedor no responde y no hay caché vigente → `provider_unavailable`; nunca se devuelven datos inventados.
- Si se usa un proveedor de fallback, se indica en `metadata.warnings` (`fallback_source_used`).
- El uso de Open-Meteo exige atribución en `metadata.attribution`.

## 3. Contrato Pydantic

```python
from enum import Enum
from pydantic import BaseModel, Field

class Granularity(str, Enum):
    daily = "daily"
    hourly = "hourly"

class WeatherVariable(str, Enum):
    temperature_2m = "temperature_2m"
    apparent_temperature = "apparent_temperature"
    precipitation_probability = "precipitation_probability"
    precipitation = "precipitation"
    wind_speed_10m = "wind_speed_10m"
    relative_humidity_2m = "relative_humidity_2m"
    shortwave_radiation = "shortwave_radiation"
    cloud_cover = "cloud_cover"
    uv_index = "uv_index"

class WeatherInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    days: int = Field(default=3, ge=1, le=7)
    granularity: Granularity = Granularity.daily
    variables: list[WeatherVariable] | None = None
    timezone: str = "Europe/Madrid"

class WeatherPoint(BaseModel):
    time: str
    values: dict[str, float | int | None]

class Location(BaseModel):
    latitude: float
    longitude: float
    elevation: float | None
    timezone: str

class WeatherOutput(BaseModel):
    location: Location
    granularity: Granularity
    points: list[WeatherPoint]
```

## 4. Matriz de casos

| Caso | Entrada | Resultado |
|---|---|---|
| Diario 2 días | `lat=40.4168`, `lon=-3.7038`, `days=2` | 2 puntos con agregados |
| Horario 1 día | `days=1`, `granularity=hourly` | 24 puntos |
| Variables filtradas | `variables=["temperature_2m","precipitation"]` | solo esas claves |
| Coordenadas invertidas | `lat=100` | error `invalid_params` |
| Días fuera de rango | `days=8` | error `invalid_params` |
| Zona inválida | `timezone=Europe/Atlantis` | error `invalid_params` |
| Proveedor caído | Open-Meteo 5xx sin caché | error `provider_unavailable` |

## 5. Golden cases

Fixture congelado `open-meteo-2026-11-13-madrid.json` (Madrid, 40.4168/−3.7038, elevación 667 m, TZ `Europe/Madrid`).

```json
{
  "input": { "latitude": 40.4168, "longitude": -3.7038, "days": 2, "granularity": "daily" },
  "output": {
    "location": { "latitude": 40.4168, "longitude": -3.7038, "elevation": 667.0, "timezone": "Europe/Madrid" },
    "granularity": "daily",
    "points": [
      {
        "time": "2026-11-13",
        "values": {
          "temperature_2m_max": 17.2,
          "temperature_2m_min": 8.4,
          "apparent_temperature_max": 16.8,
          "precipitation_probability_max": 10,
          "precipitation_sum": 0.0,
          "wind_speed_10m_max": 14.5,
          "relative_humidity_2m_mean": 61,
          "shortwave_radiation_sum": 8.9,
          "cloud_cover_mean": 35,
          "uv_index_max": 2.1
        }
      },
      {
        "time": "2026-11-14",
        "values": {
          "temperature_2m_max": 16.8,
          "temperature_2m_min": 7.9,
          "apparent_temperature_max": 16.3,
          "precipitation_probability_max": 20,
          "precipitation_sum": 0.2,
          "wind_speed_10m_max": 18.3,
          "relative_humidity_2m_mean": 66,
          "shortwave_radiation_sum": 7.4,
          "cloud_cover_mean": 52,
          "uv_index_max": 1.9
        }
      }
    ]
  }
}
```

```json
{
  "input": { "latitude": 40.4168, "longitude": -3.7038, "days": 1, "granularity": "hourly", "variables": ["temperature_2m"] },
  "output": {
    "granularity": "hourly",
    "points": [
      { "time": "2026-11-13T00:00:00+01:00", "values": { "temperature_2m": 9.1 } },
      { "time": "2026-11-13T12:00:00+01:00", "values": { "temperature_2m": 16.9 } }
    ]
  },
  "note": "El golden completo tiene 24 puntos; aquí se muestran dos"
}
```

## 6. Metadatos de respuesta

```json
{
  "source": "open_meteo",
  "source_type": "external_api",
  "source_url": "https://api.open-meteo.com/v1",
  "retrieved_at": "<now>",
  "valid_until": "<retrieved_at + 30min>",
  "result_type": "forecast",
  "is_estimated": true,
  "unit_system": "metric",
  "units": {
    "temperature": "°C",
    "precipitation": "mm",
    "wind_speed": "km/h",
    "relative_humidity": "%",
    "shortwave_radiation": "W/m²"
  },
  "timezone": "Europe/Madrid",
  "attribution": "Weather data by Open-Meteo (https://open-meteo.com)",
  "warnings": [],
  "errors": []
}
```

## 7. Composiciones

- Entrada de `sim.solar_payback` (v2): radiación y nubosidad para estimar producción.
- Usada por `alerts.contract_renewal` solo de forma contextual (no bloqueante).
- Combinada con `geo.geocode` para obtener coordenadas desde una dirección.

## 8. Decisiones pendientes

- Añadir `current` (condiciones actuales) como bloque opcional.
- Histórico meteorológico: `weather.historical` en v2 con caché de 6 h.
- Unidades imperiales: `unit_system=imperial` en v1.1.
- Verificar disponibilidad de `relative_humidity_2m_mean` y `cloud_cover_mean` con la API real; si no existen, calcularlas en servidor.
