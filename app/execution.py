"""Execute registered tools and wrap their output in the common envelope."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from app.context import ToolContext
from app.envelope import Envelope
from app.errors import ErrorCode, ToolError
from app.idempotency import deduplicated_value, idempotency_store, scoped_key
from app.metadata import build_metadata
from app.registry import ToolSpec, registry
from app.result import ToolResult


async def execute_tool(
    spec: ToolSpec,
    payload: BaseModel | object,
    ctx: ToolContext,
) -> dict[str, Any]:
    """Validate input, enforce access, run the handler and build the envelope."""
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

    idempotency_key, input_hash = _idempotency_context(spec, ctx, params)
    if idempotency_key is not None and input_hash is not None:
        record = idempotency_store.get(idempotency_key)
        if record is not None:
            if record.input_hash != input_hash:
                raise ToolError(
                    ErrorCode.CONFLICT,
                    "La idempotency_key ya se usó con parámetros distintos.",
                    details={"tool": spec.name},
                )
            return _envelope(spec, deduplicated_value(record.value))

    result = await spec.handler(params, ctx)

    if idempotency_key is not None and input_hash is not None:
        idempotency_store.put(idempotency_key, result, input_hash=input_hash)
        if isinstance(result, ToolResult):
            for alias in result.idempotency_aliases:
                idempotency_store.put(alias, result, input_hash=input_hash)

    return _envelope(spec, cast(object, result))


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


def _idempotency_context(
    spec: ToolSpec,
    ctx: ToolContext,
    params: BaseModel,
) -> tuple[str | None, str | None]:
    if spec.read_only or not spec.idempotent:
        return None, None
    raw_key = getattr(params, "idempotency_key", None)
    if not isinstance(raw_key, str) or not raw_key:
        return None, None
    return scoped_key(spec.name, ctx.company_id, raw_key), _input_hash(params)


def _input_hash(params: BaseModel) -> str:
    payload = params.model_dump(mode="json")
    payload.pop("idempotency_key", None)
    encoded = json.dumps(
        payload,
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
