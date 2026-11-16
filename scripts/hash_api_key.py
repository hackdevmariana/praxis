"""Hash an API key for PRAXIS_API_KEYS_FILE without echoing it."""

from __future__ import annotations

import getpass

from app.auth import hash_api_key


def main() -> None:
    raw_key = getpass.getpass("API key completa (key_id.secret): ")
    confirmation = getpass.getpass("Repite la API key: ")
    if not raw_key:
        raise SystemExit("La API key no puede estar vacía")
    if raw_key != confirmation:
        raise SystemExit("Las API keys no coinciden")
    print(hash_api_key(raw_key))


if __name__ == "__main__":
    main()
