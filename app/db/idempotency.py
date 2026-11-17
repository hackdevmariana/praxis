"""PostgreSQL-backed idempotency store protected by RLS."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app.clock import now
from app.db.models import IdempotencyRecordRow
from app.db.rls import company_session
from app.idempotency import IdempotencyRecord
from app.registry import registry
from app.result import ToolResult

importlib.import_module("app.tools")


class SqlAlchemyIdempotencyStore:
    """Persist idempotency results in the tenant-scoped `idempotency_records` table."""

    def __init__(self, engine: AsyncEngine, ttl: timedelta = timedelta(days=30)) -> None:
        self._engine = engine
        self._ttl = ttl

    async def get(self, key: str, *, at: datetime | None = None) -> IdempotencyRecord | None:
        company_id = _company_from_key(key)
        if company_id is None:
            return None
        moment = at or now()
        async with company_session(self._engine, company_id) as session:
            row = await session.get(IdempotencyRecordRow, key)
            if row is None or row.expires_at <= moment:
                return None
            return IdempotencyRecord(
                expires_at=row.expires_at,
                input_hash=row.input_hash,
                value=_deserialize(key, row.result),
            )

    async def put(
        self,
        key: str,
        value: Any,
        *,
        input_hash: str,
        at: datetime | None = None,
    ) -> None:
        company_id = _company_from_key(key)
        if company_id is None:
            raise ValueError("La clave de idempotencia no incluye una company_id UUID válida")
        expires_at = (at or now()) + self._ttl
        payload = _serialize(key, value)
        async with company_session(self._engine, company_id) as session:
            row = await session.get(IdempotencyRecordRow, key)
            if row is None:
                session.add(
                    IdempotencyRecordRow(
                        key=key,
                        company_id=company_id,
                        input_hash=input_hash,
                        result=payload,
                        expires_at=expires_at,
                    )
                )
            else:
                row.input_hash = input_hash
                row.result = payload
                row.expires_at = expires_at
            await session.commit()


def _company_from_key(key: str) -> UUID | None:
    parts = key.split(":")
    if len(parts) < 2 or not parts[1]:
        return None
    try:
        return UUID(parts[1])
    except ValueError:
        return None


def _serialize(key: str, value: Any) -> dict[str, Any]:
    tool = _tool_from_key(key)
    if isinstance(value, ToolResult):
        result = cast(ToolResult[BaseModel], cast(object, value))
        return {
            "type": "tool_result",
            "tool": tool,
            "data": result.data.model_dump(mode="json"),
            "warnings": list(result.warnings),
            "metadata_extra": dict(result.metadata_extra),
            "summary": result.summary,
            "idempotency_aliases": list(result.idempotency_aliases),
        }
    return {"type": "value", "tool": tool, "value": value}


def _deserialize(key: str, payload: dict[str, Any]) -> Any:
    if payload.get("type") == "value":
        return payload.get("value")
    tool = str(payload.get("tool") or _tool_from_key(key))
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload
    try:
        output_model = registry.get(tool).output_model
    except KeyError:
        return payload
    typed_data = output_model.model_validate(data)
    return ToolResult[BaseModel](
        data=typed_data,
        warnings=[str(warning) for warning in cast(list[Any], payload.get("warnings") or [])],
        metadata_extra=dict(cast(dict[str, Any], payload.get("metadata_extra") or {})),
        summary=payload.get("summary"),
        idempotency_aliases=tuple(
            str(alias) for alias in cast(list[Any], payload.get("idempotency_aliases") or [])
        ),
    )


def _tool_from_key(key: str) -> str:
    return key.split(":", 1)[0]
