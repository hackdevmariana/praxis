"""MCP server built from the same registry that powers the REST routes."""

from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, Signature
from typing import Any
from uuid import uuid4

from mcp.server.mcpserver import MCPServer
from mcp.types import Tool as MCPTool
from mcp.types import ToolAnnotations

from app.auth import AuthSettings, current_context, fallback_context
from app.errors import ToolError
from app.execution import error_envelope, execute_tool
from app.registry import ToolSpec, registry
from app.tenancy import AllowAllToolAccess, ToolAccessPolicy, apply_tool_access


class PraxisMCPServer(MCPServer):
    """MCP server that hides tools outside the authenticated tenant toolset."""

    async def list_tools(self) -> list[MCPTool]:
        tools = await super().list_tools()
        ctx = current_context()
        if ctx is None or ctx.allowed_tools is None:
            return tools
        return [tool for tool in tools if tool.name in ctx.allowed_tools]


def _handler(
    spec: ToolSpec,
    settings: AuthSettings,
    tool_access_policy: ToolAccessPolicy,
) -> Callable[..., Any]:
    async def handler(**kwargs: Any) -> dict[str, Any]:
        try:
            ctx = current_context()
            if ctx is None:
                ctx = apply_tool_access(
                    fallback_context(
                        settings,
                        request_id=uuid4().hex,
                        channel="mcp",
                    ),
                    tool_access_policy,
                )
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


def build_mcp_server(
    settings: AuthSettings | None = None,
    tool_access_policy: ToolAccessPolicy | None = None,
) -> MCPServer:
    auth_settings = settings or AuthSettings()
    access_policy = tool_access_policy or AllowAllToolAccess()
    server = PraxisMCPServer(
        name="PRAXIS",
        title="PRAXIS",
        description="Herramientas deterministas para pymes y asociaciones.",
        version="0.1.0",
    )
    for spec in registry.all():
        server.add_tool(
            _handler(spec, auth_settings, access_policy),
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
