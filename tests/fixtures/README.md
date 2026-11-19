# Test fixtures

Snapshots usados por los tests; no son datos reales de clientes.

| Archivo | Contenido | Uso |
|---|---|---|
| `ecb-2026-11-13.csv` | Tipos BCE USD/GBP/JPY para 2026-11-12 y 2026-11-13. | `test_currency_convert.py` (respuesta simulada del BCE). |
| `open-meteo-2026-11-13-madrid.json` | Previsión diaria/horaria sintética para Madrid (40.4168, -3.7038), 2026-11-13. | `test_weather_forecast.py`. |
| `invoice-F-2026-0042.pdf` | Factura PDF mínima: Suministros García S.L., base 165,00, IVA 34,65, total 199,65 EUR. | Extracción y escenarios Hotel/Polígono. |
| `invoice-blank.pdf` | PDF de una página sin texto extraíble. | Caso sin datos / baja confianza. |
| `invoice-mismatch.pdf` | Factura con total inconsistente (subtotal 100,00, IVA 21,00, total 122,00). | Caso de discrepancia y revisión. |

No hay script generador: estos ficheros se mantienen manualmente.
