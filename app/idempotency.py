"""Process-local idempotency store for effectful tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.clock import now


@dataclass(frozen=True, slots=True)
class _Entry:
    expires_at: datetime
    value: Any


class IdempotencyStore:
    """Keep successful results for a bounded period."""

    def __init__(self, ttl: timedelta = timedelta(days=30)) -> None:
        self._ttl = ttl
        self._entries: dict[str, _Entry] = {}

    def get(self, key: str, *, at: datetime | None = None) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        moment = at or now()
        if entry.expires_at <= moment:
            self._entries.pop(key, None)
            return None
        return entry.value

    def put(self, key: str, value: Any, *, at: datetime | None = None) -> None:
        moment = at or now()
        self._entries[key] = _Entry(expires_at=moment + self._ttl, value=value)

    def clear(self) -> None:
        self._entries.clear()


idempotency_store = IdempotencyStore()
