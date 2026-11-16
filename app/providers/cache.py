"""Small in-memory TTL cache for external provider responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.clock import now

_CACHES: list[TTLCache[Any]] = []


@dataclass(frozen=True, slots=True)
class CacheEntry[ValueT]:
    """A cached value together with its retrieval window."""

    value: ValueT
    retrieved_at: datetime
    valid_until: datetime


class TTLCache[ValueT]:
    """Process-local cache invalidated by `valid_until`, not by wall-clock TTL."""

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry[ValueT]] = {}
        _CACHES.append(self)

    def get(self, key: str) -> CacheEntry[ValueT] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if now() >= entry.valid_until:
            del self._entries[key]
            return None
        return entry

    def set(self, key: str, value: ValueT, ttl: timedelta) -> CacheEntry[ValueT]:
        retrieved_at = now()
        entry = CacheEntry(
            value=value,
            retrieved_at=retrieved_at,
            valid_until=retrieved_at + ttl,
        )
        self._entries[key] = entry
        return entry

    def clear(self) -> None:
        self._entries.clear()


def clear_all_caches() -> None:
    """Clear every provider cache (used by tests)."""
    for cache in _CACHES:
        cache.clear()
