---
estado: v2
version: 0.1.0
---

# Enrutamiento y capa de canal

> **Estado: v2.** En el MVP, el enrutamiento lo hace el LLM del arnés del cliente al seleccionar una tool MCP. Este documento define el diseño de la capa de canal externa y el artefacto `intents.yaml`, no forma parte de `praxis-core`.

## Principio

`praxis-core` **no enruta**. Recibe una tool ya elegida y argumentos tipados. El enrutamiento (entender una frase y decidir qué tool ejecutar) vive en la **capa de canal**, que es externa y opcional.

Esto permite dos modos de uso:

| Modo | Quién enruta | Cuándo |
|---|---|---|
| **MCP (recomendado)** | El LLM del arnés del cliente | Producción general; paga tokens el cliente |
| **Gateway determinista** | regex / `rapidfuzz` / semantic-router | Bots WhatsApp/Telegram con peticiones triviales; ahorra tokens |

## Gateway determinista (v2)

Objetivo: resolver sin LLM las peticiones frecuentes y de bajo riesgo ("¿precio de la luz hoy?", "¿cuánto es el IVA de 1500?", "¿qué tiempo hará mañana en Logroño?").

Flujo:

```txt
mensaje
  → normalización (Unidecode, minúsculas, limpieza)
  → detección de intención (regex → fuzzy → semantic-router)
  → extracción de entidades (fechas con dateparser, importes, municipios)
  → invocación de praxis-core (tool + parámetros)
  → formateo (formatters con Babel)
  → respuesta al canal
```

Si la confianza es baja o no hay intención, el gateway delega en el LLM del arnés (fallback) o pide aclaración.

## Normalización

1. **Unicode/acentos:** `Unidecode` ("Barcelóna" → "barcelona").
2. **Mayúsculas/minúsculas y espacios:** colapsar y recortar.
3. **Sinónimos:** diccionario por intención ("iva", "impuesto", "vat").
4. **Números y monedas:** normalizar separadores (`1.500,50 €`).
5. **Fechas:** `dateparser` con `languages=["es","en"]`, `TIMEZONE="Europe/Madrid"`, `RETURN_AS_TIMEZONE_AWARE=True`.
6. **Municipios:** `rapidfuzz` contra el dataset de 8.131 municipios con código INE.

## `intents.yaml`

Artefacto **compartido** (no código de core) que describe las intenciones enroutables y su correspondencia con tools. Sirve al gateway y, en el futuro, a la generación de ejemplos para el catálogo MCP.

```yaml
version: 1

datetime:
  today:
    description: Obtener la fecha actual.
    tool: datetime.calc
    params:
      operation: today
    examples:
      - "¿qué día es hoy?"
      - "dime la fecha de hoy"

finance:
  vat:
    description: Calcular IVA de una cantidad.
    tool: finance.vat
    params:
      operation: add
    examples:
      - "¿cuánto es el IVA de 1500?"
      - "súmale el 21% a 300"

weather:
  forecast:
    description: Consultar previsiones meteorológicas.
    tool: weather.forecast
    requires:
      - location
    examples:
      - "¿qué tiempo hará mañana en Logroño?"
```

Reglas del artefacto:

- Una intención puede mapear a una tool con parámetros fijos o variables.
- Declara las entidades requeridas (`requires`).
- Los `examples` son frases de referencia para fuzzy/semantic-router y para tests.
- No contiene lógica de ejecución: el gateway lo interpreta.

## Detección por niveles (v2)

1. **Regex exacta:** patrones de alta confianza y coste mínimo.
2. **Fuzzy (`rapidfuzz`):** similitud contra ejemplos y vocabulario (municipios, monedas, verbos).
3. **Semantic-router:** embeddings locales (`fastembed`, BGE-small) para paráfrasis. Se activa solo si las dos anteriores fallan.
4. **Fallback LLM:** el gateway pide al arnés que seleccione tool.

Cada nivel registra `confidence` y `execution_method` (`deterministic`, `semantic`, `llm`) para auditoría.

## Riesgos y reglas

- **No** usar `dateparser` para cálculos de negocio: solo para extraer fechas de mensajes; los cálculos usan `datetime.calc` con fechas ya normalizadas.
- **No** aleatorizar plantillas en producción (ver [`08-formatting.md`](08-formatting.md)).
- Toda respuesta del gateway debe poder trazarse a una ejecución de `praxis-core` con su `request_id`.
- El gateway nunca implementa cálculos propios: solo enruta, extrae entidades y formatea.

## Qué NO entra en el MVP

- `intents.yaml`, regex, fuzzy, semantic-router y formatters de canal.
- El MVP se limita al modo MCP: el LLM del cliente selecciona la tool.

El diseño se mantiene documentado para no acoplar el core y para que la comunidad pueda construir gateways sin tocar `praxis-core`.
