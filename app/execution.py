"""Execute registered tools and wrap their output in the common envelope."""

from typing import Any, cast

from pydantic import BaseModel, ValidationError

from app.context import ToolContext
from app.envelope import Envelope
from app.errors import ErrorCode, ToolError
from app.metadata import build_metadata
from app.registry import ToolSpec, registry
from app.result import ToolResult


async def execute_tool(
    spec: ToolSpec,
    payload: BaseModel | object,
    ctx: ToolContext,
) -> dict[str, Any]:
    """Validate input, run the handler and return a JSON-ready envelope."""
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

    result = await spec.handler(params, ctx)
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
