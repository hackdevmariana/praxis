---
estado: MVP
version: 0.1.0
---

# APIs externas

Cada proveedor externo se describe con una **ficha declarativa** (bloque YAML en este documento): autenticación, límites, caché, fallback, términos de servicio y política de redistribución. La ficha es el contrato de referencia; el código mantiene sus constantes y políticas sincronizadas con ella.

## Reglas generales

- **Claves por instalación.** Cada despliegue usa sus propias claves en `.env`; nunca se incluyen claves en el repositorio.
- **Redistribución.** Si un proveedor no permite redistribuir datos, PRAXIS no los cachea de forma compartida entre tenants ni los reexpone fuera de la ejecución.
- **Fallback.** Todo proveedor crítico declara `fallback_providers`. Si falla, se intenta el siguiente y se marca `metadata.warnings`.
- **Circuit breaker.** Tras N fallos, el proveedor pasa a `open` y se sirve caché o fallback; recuperación en `half_open`.
- **Caché por `valid_until`.** La caché se invalida por vigencia, no por tiempo fijo arbitrario.
- **Atribución.** Si `attribution_required`, el texto de atribución viaja en `metadata.attribution`.

## MVP

### Open-Meteo (meteorología)

```yaml
provider_id: open_meteo
display_name: "Open-Meteo"
base_url: "https://api.open-meteo.com/v1"
authentication: none
terms_of_service: "https://open-meteo.com/en/terms"
license: "CC BY 4.0"
redistribution_allowed: true
redistribution_conditions: "Con atribución"
commercial_use_allowed: true
rate_limits:
  free: "10.000 peticiones/día"
availability_target: "99.5%"
availability_status_page: "https://status.open-meteo.com"
fallback_providers: ["aemet"]
cache_policy:
  current: "5min"
  forecast: "30min"
  historical: "6h"
attribution_required: true
attribution_text: "Weather data by Open-Meteo (https://open-meteo.com)"
personal_data_collected: false
personal_data_note: "Solo coordenadas, sin PII"
circuit_breaker:
  failure_threshold: 5
  recovery_timeout_seconds: 60
  half_open_max_calls: 3
```

Devuelve en una sola consulta temperatura, sensación térmica, probabilidad de lluvia, precipitación, viento, humedad, radiación solar, nubosidad e índice UV.

### BCE — tipos de cambio

```yaml
provider_id: ecb
display_name: "Banco Central Europeo"
base_url: "https://data-api.ecb.europa.eu"
authentication: none
terms_of_service: "https://www.ecb.europa.eu/services/using-our-site/html/index.en.html"
license: "Uso público con atribución"
redistribution_allowed: true
rate_limits:
  free: "Uso razonable"
fallback_providers: []
cache_policy:
  daily_rates: "12h"
attribution_required: true
attribution_text: "Tipos de cambio de referencia del BCE"
personal_data_collected: false
circuit_breaker:
  failure_threshold: 5
  recovery_timeout_seconds: 120
  half_open_max_calls: 2
notes: |
  Cubre monedas fiduciarias de referencia. BTC y otras criptomonedas
  no están cubiertas y quedan fuera de v1.
```

### CartoCiudad (geocoding)

```yaml
provider_id: cartociudad
display_name: "CartoCiudad (IGN)"
base_url: "https://www.cartociudad.es/geocoder/api"
authentication: none
terms_of_service: "https://www.cartociudad.es/portal/web/guest/condiciones-de-uso"
license: "Uso público"
redistribution_allowed: false
rate_limits:
  free: "Uso razonable, sin límite estricto de 1 req/s"
fallback_providers: ["nominatim"]
cache_policy:
  forward: "7d"
  reverse: "7d"
attribution_required: true
attribution_text: "Geocodificación: CartoCiudad (IGN)"
personal_data_collected: false
circuit_breaker:
  failure_threshold: 5
  recovery_timeout_seconds: 60
  half_open_max_calls: 3
notes: |
  Geocoder oficial español, preferido sobre Nominatim para direcciones
  de España. Nominatim se usa solo como fallback y respetando su
  política de 1 req/s y User-Agent identificable.
```

## Backlog / v2

Fichas resumidas para herramientas previstas. Se completan al implementarlas.

| Proveedor | Datos | Auth | Límite / coste | Uso previsto | Estado |
|---|---|---|---|---|---|
| ESIOS (REE) | Precio horario PVPC, mix | Token personal (email) | Gratuito | `energy.pvpc_hourly` | v2 |
| OMIE | Mercado mayorista | Descarga/API | Gratuito | `energy.omie` | v2 |
| INE | IPC, PIB, paro, salarios, CNAE | Ninguna | Gratuito | `macro.*` | v2 |
| Banco de España | Euríbor, tipos | Ninguna | Gratuito | `macro.euribor` | v2 |
| AEMET OpenData | Meteorología oficial | API key | Gratuito | Fallback clima | v2 |
| CNMC | Tarifas y peajes | Ninguna | Gratuito | Comparativa eléctrica | v2 |
| PVGIS (JRC) | Producción fotovoltaica | Ninguna | Gratuito | Simulador solar | v2 |
| Catastro (OVC) | Referencia ↔ dirección | Ninguna | Gratuito | Superficie, autoconsumo | v2 |
| BDNS | Subvenciones | Ninguna | Gratuito | Buscador de ayudas | v2 |
| VIES | Validación NIF UE | Ninguna | Gratuito | Validación proveedores | v2 |
| BORME / Registro Concursal | Concursos, administradores | Scraping / pago | Limitado | Alertas legales | backlog |
| OSRM | Rutas y distancias | Ninguna | ~1 req/s (instancia pública) | `geo.route` | v2 |
| RDAP | WHOIS de dominios | Ninguna | Gratuito | Auditoría web | backlog |
| PageSpeed Insights | Rendimiento web | API key | Gratuito | Auditoría web | backlog |
| MIBGAS / ENTSOG | Gas natural | Varía | Gratuito / pago | Energía gas | backlog |
| REGCON (MITES) | Convenios colectivos | Scraping | Gratuito | Convenio aplicable | backlog |
| GoCardless (PSD2) | Movimientos bancarios | OAuth | Tier gratuito | Tesorería | v2 |

## Gestión de errores y metadatos

Cuando un proveedor falla:

1. Se intenta `fallback_source_id`.
2. Si tampoco responde, se devuelve `success: false` con `metadata.errors` y `metadata.warnings`.
3. Nunca se inventan datos: si no hay dato vigente, la respuesta lo declara explícitamente.

Campos de metadatos obligatorios por respuesta externa:

- `source` (proveedor concreto, no genérico), `source_type`.
- `retrieved_at`, `valid_until`.
- `is_estimated`, `confidence` (si aplica).
- `unit`, `currency`, `timezone`.
- `attribution` (si el proveedor lo exige).
- `warnings`, `errors`.

Ver el contrato de respuesta en [`01-architecture.md`](01-architecture.md) y el modelo `DataSource` en [`05-data-models.md`](05-data-models.md).
