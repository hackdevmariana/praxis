---
estado: MVP
version: 0.1.0
---

# Formato de respuesta y canales

## Principio

`praxis-core` devuelve **JSON limpio + metadatos**. El formateo a texto humano es una **capacidad opcional y externa** (capa de canal o módulo de formato), nunca lógica dentro de la tool. Si el consumidor es un LLM vía MCP, **no se formatea**: se entrega el JSON.

Esto cumple los dos objetivos:

- **Anti-alucinación:** el texto se construye a partir de datos ya calculados.
- **Ahorro de tokens:** el LLM recibe la estructura mínima necesaria, no prosa que deba re-parsear.

## Modos de respuesta

| Modo | Consumidor | Salida |
|---|---|---|
| `json` | MCP / agente | Sobre JSON completo con metadatos |
| `compact` | MCP / agente | JSON reducido + `summary` corto (ahorro de tokens) |
| `text` | Canal humano | Texto determinista formateado con Babel |
| `both` | Gateway / auditoría | JSON + texto |

Modos de tono/nivel para canales humanos:

- `short` — una frase.
- `normal` — resultado + contexto mínimo.
- `detailed` — resultado + desglose.
- `executive` — resultado + implicación de negocio.
- `technical` — resultado + supuestos y fuentes.
- `auditor` — incluye metadatos completos y trazabilidad.

## Sobre de respuesta

```json
{
  "success": true,
  "tool": "finance.vat",
  "tool_version": "1.0.0",
  "data": {
    "base_amount": "1000.00",
    "vat_rate": "21",
    "vat_amount": "210.00",
    "total_amount": "1210.00",
    "currency": "EUR"
  },
  "metadata": {
    "source": "deterministic",
    "source_type": "deterministic",
    "retrieved_at": "2026-11-12T12:00:00Z",
    "valid_until": null,
    "result_type": "calculation",
    "is_estimated": false,
    "confidence": null,
    "unit_system": "metric",
    "timezone": "Europe/Madrid",
    "warnings": [],
    "errors": [],
    "legal_disclaimer_required": false
  },
  "summary": "IVA (21%) de 1.000,00 € = 210,00 €. Total: 1.210,00 €."
}
```

- `summary` es **opcional** y siempre derivado de `data`, nunca generado por LLM.
- Importes como **string decimal** para preservar exactitud.
- `legal_disclaimer_required` lo fija la tool; el formateador lo inyecta obligatoriamente.

## Formateo determinista

Reglas:

1. **Sin aleatoriedad en producción.** Una plantilla determinista por `(canal, tono, idioma, nivel)`.
2. **Babel** para monedas, fechas y números: `1.500,50 €`, `12/11/2026`.
3. **`zoneinfo`** para zonas horarias; nunca offsets hardcodeados.
4. **Idioma** según `Language` del usuario; castellano por defecto.
5. **Atribución** de proveedor si `metadata.attribution` está presente.
6. **Warnings** visibles cuando el dato es estimado, parcial o de fallback.

### Estructura de un formateador

```txt
formatting/
└── finance/
    └── vat/
        ├── templates.py    # plantillas deterministas por tono/idioma
        └── formatter.py    # selección de plantilla + Babel
```

Separación de responsabilidades:

- **Tool (`praxis-core`):** calcula y devuelve `data` + `metadata`.
- **Formatter (capa de canal):** convierte `data` en texto. No calcula.
- **LLM:** puede reescribir el `summary` para el usuario, pero **no recalcula** importes ni fechas.

### Ejemplo de plantilla

```python
VAT_TEMPLATES = {
    ("es", "short"): "El IVA ({vat_rate}%) de {base_amount} es {vat_amount}. Total: {total_amount} {currency}.",
    ("es", "detailed"): (
        "Base imponible: {base_amount} {currency}. "
        "IVA ({vat_rate}%): {vat_amount} {currency}. "
        "Total: {total_amount} {currency}."
    ),
}
```

La selección es por clave `(idioma, tono)`; no se elige al azar.

## Canales

| Canal | Formato | Notas |
|---|---|---|
| MCP / agente | `json` o `compact` | Sin texto decorativo |
| WhatsApp / Telegram | `text`, `short` | Mensajes breves, sin tablas anchas |
| Email | `text`, `normal`/`detailed` | Más contexto y atribución |
| Web / panel | `json` + render en cliente | El backend no genera HTML de UI |
| PDF (documentos) | HTML → PDF (`WeasyPrint`) | Plantillas de documento, no de chat |

## Disclaimer legal

- Las tools legales, laborales y fiscales marcan `legal_disclaimer_required: true`.
- El formateador inyecta siempre el aviso, en cualquier tono:
  > «Esta información es orientativa y no constituye asesoramiento jurídico, fiscal ni laboral. Verifique con un profesional.»
- El aviso se registra en `ToolExecutionLog.legal_disclaimer_shown`.

## Ahorro de tokens

- `compact` elimina campos vacíos y anida solo lo esencial.
- Se ofrecen resúmenes por tool pensados para el agente (p. ej. tabla de ofertas ya ordenada) para que el LLM no tenga que transformar datos.
- Nunca se envía al LLM texto formateado más el JSON: se elige uno.
- Se documenta el tamaño medio de respuesta por tool en [`11-success-metrics.md`](11-success-metrics.md).
