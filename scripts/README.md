# Scripts

Utilidades de desarrollo, datos y operación local. Se ejecutan desde la raíz del repositorio con `uv run`.

| Script | Uso | Comando |
|---|---|---|
| `check_markdown.py` | Valida enlaces, anclas y frontmatter de Markdown. | `uv run python scripts/check_markdown.py` |
| `generate_holidays.py` | Regenera `app/data/holidays_es.json` desde `python-holidays`. | `uv run python scripts/generate_holidays.py` |
| `hash_api_key.py` | Genera el hash Argon2id de una API key sin mostrarla. | `uv run python scripts/hash_api_key.py` |
| `issue_token.py` | Emite un JWT de desarrollo para probar REST/MCP. | Ver ejemplo abajo. |
| `seed_demo.py` | Crea o actualiza los tenants demo y las fuentes globales. | `uv run python scripts/seed_demo.py` |

## Ejemplos

Emitir un token de desarrollo:

```bash
export PRAXIS_AUTH_REQUIRED=true
export PRAXIS_JWT_SECRET='secret-de-al-menos-32-caracteres'
uv run python scripts/issue_token.py \
  --subject demo \
  --company-id 11111111-1111-4111-8111-111111111111 \
  --role admin \
  --scope '*'
```

Cargar datos demo con una URL explícita:

```bash
uv run python scripts/seed_demo.py \
  --database-url 'postgresql+asyncpg://praxis:praxis@localhost:5432/praxis'
```

Volver al [índice de documentación](../docs/README.md).
