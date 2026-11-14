"""Tool result wrapper carrying data plus response metadata hints."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field


class ToolResult[DataT: BaseModel](BaseModel):
    """Data returned by a tool plus warnings and metadata for the envelope."""

    data: DataT
    warnings: list[str] = Field(default_factory=lambda: [])
    metadata_extra: dict[str, Any] = Field(default_factory=lambda: {})
    summary: str | None = None


def tool_result[DataT: BaseModel](
    data: DataT,
    *,
    warnings: Sequence[str] = (),
    metadata_extra: Mapping[str, Any] | None = None,
    summary: str | None = None,
) -> ToolResult[DataT]:
    """Build a typed ToolResult without repeating generic parameters."""
    return ToolResult[DataT](
        data=data,
        warnings=list(warnings),
        metadata_extra=dict(metadata_extra or {}),
        summary=summary,
    )
