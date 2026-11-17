"""Execute registered tools, audit them and wrap their output in the envelope."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from app.audit import ExecutionLogRecord, get_execution_log_store
from app.context import ToolContext
from app.envelope import Envelope
from app.errors import ErrorCode, ToolError
from app.idempotency import deduplicated_value, idempotency_store, scoped_key
from app.metadata import build_metadata
from app.registry import ToolSpec, registry
from app.result import ToolResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ExecutionState:
    input_hash: str
    idempotency_key: str | None = None
    idempotency_hit: bool = False


async def execute_tool(
    spec: ToolSpec,
    payload: BaseModel | object,
    ctx: ToolContext,
) -> dict[str, Any]:
    """Validate input, enforce access, run the handler and build the envelope."""
    started = perf_counter()
    state = _ExecutionState(input_hash=_payload_hash(payload))
    try:
        envelope = await _execute(spec, payload, ctx, state)
    except ToolError as error:
        await _write_log(
            spec,
            ctx,
            state,
            started,
            success=False,
            error={"code": error.code},
        )
        raise
    except Exception:
        logger.exception("Tool %s falló inesperadamente", spec.name)
        await _write_log(
            spec,
            ctx,
            state,
            started,
            success=False,
            error={"code": ErrorCode.INTERNAL_ERROR.value},
        )
        raise

    await _write_log(spec, ctx, state, started, success=True, envelope=envelope)
    return envelope


async def execute_by_name(
    name: str,
    payload: object,
    ctx: ToolContext,
) -> dict[str, Any]:
    """Resolve a tool by name and execute it."""
    try:
        spec = registry.get(name)
    except KeyError as error:
        raise ToolError(
            ErrorCode.TOOL_NOT_AVAILABLE,
            f"La tool {name!r} no está registrada.",
        ) from error
    return await execute_tool(spec, payload, ctx)


def error_envelope(spec: ToolSpec, error: ToolError) -> dict[str, Any]:
    """Build a failed envelope so MCP clients still receive structured errors."""
    return Envelope(
        success=False,
        tool=spec.name,
        tool_version=spec.version,
        data=None,
        metadata=build_metadata(
            result_type="error",
            errors=[error.to_dict()],
        ),
    ).to_dict()


async def _execute(
    spec: ToolSpec,
    payload: BaseModel | object,
    ctx: ToolContext,
    state: _ExecutionState,
) -> dict[str, Any]:
    if ctx.allowed_tools is not None and spec.name not in ctx.allowed_tools:
        raise ToolError(
            ErrorCode.TOOL_NOT_AVAILABLE,
            f"La tool {spec.name} no está activa para el tenant.",
            details={"tool": spec.name},
        )
    missing_scopes = [
        permission for permission in spec.permissions if not ctx.has_scope(permission)
    ]
    if missing_scopes:
        raise ToolError(
            ErrorCode.PERMISSION_DENIED,
            "El contexto no tiene los scopes necesarios para ejecutar la tool.",
            details={
                "required": list(spec.permissions),
                "missing": missing_scopes,
            },
        )
    if spec.requires_confirmation and not ctx.confirmed:
        raise ToolError(
            ErrorCode.CONFIRMATION_REQUIRED,
            f"{spec.name} requiere confirmación humana.",
        )

    if isinstance(payload, spec.input_model):
        params = payload
    else:
        try:
            params = spec.input_model.model_validate(payload)
        except ValidationError as error:
            raise ToolError(
                ErrorCode.INVALID_PARAMS,
                "Los parámetros no cumplen el esquema de la tool.",
                details={
                    "errors": error.errors(
                        include_url=False,
                        include_context=False,
                        include_input=False,
                    )
                },
            ) from error

    state.input_hash = _payload_hash(params)
    state.idempotency_key = _idempotency_key(spec, ctx, params)
    if state.idempotency_key is not None:
        record = idempotency_store.get(state.idempotency_key)
        if record is not None:
            if record.input_hash != state.input_hash:
                raise ToolError(
                    ErrorCode.CONFLICT,
                    "La idempotency_key ya se usó con parámetros distintos.",
                    details={"tool": spec.name},
                )
            state.idempotency_hit = True
            return _envelope(spec, deduplicated_value(record.value))

    result = await spec.handler(params, ctx)

    if state.idempotency_key is not None:
        idempotency_store.put(state.idempotency_key, result, input_hash=state.input_hash)
        if isinstance(result, ToolResult):
            for alias in result.idempotency_aliases:
                idempotency_store.put(alias, result, input_hash=state.input_hash)

    return _envelope(spec, cast(object, result))


async def _write_log(
    spec: ToolSpec,
    ctx: ToolContext,
    state: _ExecutionState,
    started: float,
    *,
    success: bool,
    error: dict[str, Any] | None = None,
    envelope: dict[str, Any] | None = None,
) -> None:
    metadata = cast(dict[str, Any], envelope.get("metadata", {})) if envelope else {}
    raw_warnings = cast(list[Any], metadata.get("warnings") or [])
    warnings = tuple(str(warning) for warning in raw_warnings)
    entry = ExecutionLogRecord(
        request_id=ctx.request_id,
        tool_name=spec.name,
        tool_version=spec.version,
        user_id=ctx.user_id,
        company_id=ctx.company_id,
        channel=ctx.channel,
        input_hash=state.input_hash,
        execution_time_ms=int((perf_counter() - started) * 1000),
        success=success,
        error=error,
        idempotency_key=state.idempotency_key,
        idempotency_hit=state.idempotency_hit,
        source=metadata.get("source"),
        source_type=metadata.get("source_type"),
        result_type=metadata.get("result_type"),
        warnings=warnings,
        summary=envelope.get("summary") if envelope else None,
    )
    try:
        await get_execution_log_store().record(entry)
    except Exception:
        logger.exception("No se pudo registrar ToolExecutionLog de %s", spec.name)


def _idempotency_key(spec: ToolSpec, ctx: ToolContext, params: BaseModel) -> str | None:
    if spec.read_only or not spec.idempotent:
        return None
    raw_key = getattr(params, "idempotency_key", None)
    if not isinstance(raw_key, str) or not raw_key:
        return None
    return scoped_key(spec.name, ctx.company_id, raw_key)


def _payload_hash(payload: object) -> str:
    value: Any = payload
    if isinstance(payload, BaseModel):
        value = payload.model_dump(mode="json")
    elif isinstance(payload, Mapping):
        value = dict(cast(Mapping[object, Any], payload))
    if isinstance(value, dict):
        mapping = cast(dict[str, Any], value)
        mapping.pop("idempotency_key", None)
        value = mapping
    encoded = json.dumps(
        value,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _envelope(spec: ToolSpec, result: object) -> dict[str, Any]:
    if isinstance(result, ToolResult):
        tool_result = cast("ToolResult[BaseModel]", result)
        data = tool_result.data
        warnings = tool_result.warnings
        metadata_extra = tool_result.metadata_extra
        summary = tool_result.summary
    else:
        data = result
        warnings = []
        metadata_extra = {}
        summary = None

    return Envelope(
        success=True,
        tool=spec.name,
        tool_version=spec.version,
        data=data,
        metadata=build_metadata(warnings=warnings, **metadata_extra),
        summary=summary,
    ).to_dict()
