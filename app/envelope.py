"""Common response envelope shared by every tool."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field


class ResponseMetadata(BaseModel):
    """Traceability metadata attached to every tool response."""

    model_config = ConfigDict(extra="allow")

    source: str
    source_type: str
    retrieved_at: datetime
    valid_until: datetime | None = None
    result_type: str
    is_estimated: bool = False
    confidence: float | None = None
    unit_system: str = "metric"
    timezone: str = "Europe/Madrid"
    warnings: list[str] = Field(default_factory=lambda: [])
    errors: list[dict[str, Any]] = Field(default_factory=lambda: [])
    legal_disclaimer_required: bool = False


class Envelope(BaseModel):
    """The `{ success, tool, tool_version, data, metadata }` contract."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    tool: str
    tool_version: str
    data: Any
    metadata: ResponseMetadata
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict with Decimals and dates as strings."""
        payload = _jsonable(self)
        if self.summary is None:
            payload.pop("summary", None)
        return payload


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {key: _jsonable(item) for key, item in value.model_dump().items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, Any], value)
        return {str(key): _jsonable(item) for key, item in mapping.items()}
    if isinstance(value, list | tuple | set | frozenset):
        items = cast(Iterable[Any], value)
        return [_jsonable(item) for item in items]
    return value
