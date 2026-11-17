"""Injectable execution audit trail for tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import ToolExecutionLogRow
from app.db.rls import company_session


@dataclass(frozen=True, slots=True)
class ExecutionLogRecord:
    request_id: str
    tool_name: str
    tool_version: str
    user_id: str | None
    company_id: str | None
    channel: str
    input_hash: str
    execution_time_ms: int
    success: bool
    error: dict[str, Any] | None = None
    idempotency_key: str | None = None
    idempotency_hit: bool = False
    source: str | None = None
    source_type: str | None = None
    result_type: str | None = None
    warnings: tuple[str, ...] = ()
    summary: str | None = None


class ExecutionLogStore(Protocol):
    async def record(self, entry: ExecutionLogRecord) -> None: ...


class NoopExecutionLogStore:
    async def record(self, entry: ExecutionLogRecord) -> None:
        return None


class InMemoryExecutionLogStore:
    def __init__(self) -> None:
        self.records: list[ExecutionLogRecord] = []

    async def record(self, entry: ExecutionLogRecord) -> None:
        self.records.append(entry)

    def clear(self) -> None:
        self.records.clear()


class SqlAlchemyExecutionLogStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record(self, entry: ExecutionLogRecord) -> None:
        if entry.company_id is None:
            return
        try:
            company_id = UUID(entry.company_id)
        except ValueError:
            return
        async with company_session(self._engine, company_id) as session:
            session.add(
                ToolExecutionLogRow(
                    request_id=entry.request_id,
                    tool_name=entry.tool_name,
                    tool_version=entry.tool_version,
                    user_id=entry.user_id,
                    company_id=company_id,
                    channel=entry.channel,
                    input_hash=entry.input_hash,
                    execution_time_ms=entry.execution_time_ms,
                    success=entry.success,
                    error=entry.error,
                    idempotency_key=entry.idempotency_key,
                    idempotency_hit=entry.idempotency_hit,
                    source=entry.source,
                    source_type=entry.source_type,
                    result_type=entry.result_type,
                    warnings=list(entry.warnings),
                    summary=entry.summary,
                )
            )
            await session.commit()


_store: ExecutionLogStore = NoopExecutionLogStore()


def set_execution_log_store(store: ExecutionLogStore) -> None:
    global _store
    _store = store


def get_execution_log_store() -> ExecutionLogStore:
    return _store
