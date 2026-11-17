"""Central idempotency store for effectful tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from pydantic import BaseModel

from app.clock import now
from app.result import ToolResult


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    """Stored result plus the input fingerprint that produced it."""

    expires_at: datetime
    input_hash: str
    value: Any


class IdempotencyStore:
    """Keep successful results for a bounded period."""

    def __init__(self, ttl: timedelta = timedelta(days=30)) -> None:
        self._ttl = ttl
        self._entries: dict[str, IdempotencyRecord] = {}

    def get(self, key: str, *, at: datetime | None = None) -> IdempotencyRecord | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        moment = at or now()
        if entry.expires_at <= moment:
            self._entries.pop(key, None)
            return None
        return entry

    def put(
        self,
        key: str,
        value: Any,
        *,
        input_hash: str,
        at: datetime | None = None,
    ) -> None:
        moment = at or now()
        self._entries[key] = IdempotencyRecord(
            expires_at=moment + self._ttl,
            input_hash=input_hash,
            value=value,
        )

    def clear(self) -> None:
        self._entries.clear()


def scoped_key(tool: str, company_id: str | None, *parts: object) -> str:
    """Build a tenant-scoped idempotency key."""
    return ":".join((tool, company_id or "", *(str(part) for part in parts)))


def deduplicated_value(value: Any) -> Any:
    """Mark a stored value as a deduplicated response."""
    if isinstance(value, ToolResult):
        result = cast(ToolResult[BaseModel], cast(object, value))
        data = _deduplicated_data(result.data)
        metadata_extra = {**result.metadata_extra, "effect": "deduplicated"}
        return result.model_copy(update={"data": data, "metadata_extra": metadata_extra})
    return _deduplicated_data(value)


def _deduplicated_data(value: Any) -> Any:
    if isinstance(value, BaseModel) and "deduplicated" in type(value).model_fields:
        return value.model_copy(update={"deduplicated": True})
    return value


idempotency_store = IdempotencyStore()
