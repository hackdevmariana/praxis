"""Helper to build the common response metadata block."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from app.clock import MADRID, now
from app.envelope import ResponseMetadata


def build_metadata(
    *,
    source: str = "deterministic",
    source_type: str = "deterministic",
    retrieved_at: datetime | None = None,
    valid_until: datetime | None = None,
    result_type: str = "calculation",
    is_estimated: bool = False,
    confidence: float | None = None,
    unit_system: str = "metric",
    timezone: str = MADRID.key,
    warnings: Sequence[str] = (),
    errors: Sequence[Mapping[str, Any]] = (),
    legal_disclaimer_required: bool = False,
    **extra: Any,
) -> ResponseMetadata:
    """Build metadata with project defaults; `extra` carries tool-specific fields."""
    payload: dict[str, Any] = {
        "source": source,
        "source_type": source_type,
        "retrieved_at": retrieved_at or now(),
        "valid_until": valid_until,
        "result_type": result_type,
        "is_estimated": is_estimated,
        "confidence": confidence,
        "unit_system": unit_system,
        "timezone": timezone,
        "warnings": list(warnings),
        "errors": [dict(error) for error in errors],
        "legal_disclaimer_required": legal_disclaimer_required,
    }
    payload.update(extra)
    return ResponseMetadata.model_validate(payload)
