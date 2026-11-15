"""MCP server built from the same registry that powers the REST routes."""

from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, Signature
from typing import Any
from uuid import uuid4

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.context import ToolContext
from app.errors import ToolError
from app.execution import error_envelope, execute_tool
from app.registry import ToolSpec, registry


def _handler(spec: ToolSpec) -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> dict[str, Any]:
        ctx = ToolContext(request_id=uuid4().hex, channel="mcp")
        try:
            return await execute_tool(spec, kwargs, ctx)
        except ToolError as error:
            return error_envelope(spec, error)

    handler.__name__ = f"mcp_{spec.name.replace('.', '_')}"
    handler.__doc__ = spec.description
    parameters = [
        Parameter(
            name,
            Parameter.POSITIONAL_OR_KEYWORD,
            default=(
                Parameter.empty
                if field.is_required()
                else field.get_default(call_default_factory=True)
            ),
            annotation=field.rebuild_annotation(),
        )
        for name, field in spec.input_model.model_fields.items()
    ]
    parameters.sort(key=lambda parameter: parameter.default is not Parameter.empty)
    handler.__signature__ = Signature(parameters=parameters, return_annotation=dict[str, Any])
    return handler


def build_mcp_server() -> MCPServer:
    server = MCPServer(
        name="PRAXIS",
        title="PRAXIS",
        description="Herramientas deterministas para pymes y asociaciones.",
        version="0.1.0",
    )
    for spec in registry.all():
        server.add_tool(
            _handler(spec),
            name=spec.name,
            title=spec.title,
            description=spec.description,
            annotations=ToolAnnotations(
                title=spec.title,
                read_only_hint=spec.read_only,
                destructive_hint=not spec.read_only and spec.requires_confirmation,
                idempotent_hint=spec.idempotent,
                open_world_hint=spec.open_world,
            ),
        )
    return server
