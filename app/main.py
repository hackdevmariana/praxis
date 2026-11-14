"""FastAPI application and MCP server for the PRAXIS tool catalog."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from inspect import Parameter, Signature
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app import tools
from app.context import ToolContext
from app.errors import ToolError
from app.execution import error_envelope, execute_tool
from app.mcp_server import build_mcp_server
from app.registry import ToolSpec, registry

API_VERSION = "0.1.0"
_TOOL_MODULES = tools  # imported for registration side effects


def _tool_endpoint(spec: ToolSpec) -> Callable[..., Any]:
    async def endpoint(**kwargs: Any) -> dict[str, Any]:
        request = cast(Request, kwargs["request"])
        params = cast(BaseModel, kwargs["params"])
        ctx = ToolContext(
            request_id=request.headers.get("x-request-id") or uuid4().hex,
            channel="http",
        )
        try:
            return await execute_tool(spec, params, ctx)
        except ToolError as error:
            return error_envelope(spec, error)

    endpoint.__name__ = f"tool_{spec.name.replace('.', '_')}"
    endpoint.__doc__ = spec.description
    signature = Signature(
        parameters=[
            Parameter("request", Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
            Parameter(
                "params",
                Parameter.POSITIONAL_OR_KEYWORD,
                annotation=spec.input_model,
            ),
        ],
        return_annotation=dict[str, Any],
    )
    endpoint.__signature__ = signature
    return endpoint


def _register_tool_routes(app: FastAPI) -> None:
    for spec in registry.all():
        app.add_api_route(
            f"/api/tools/{spec.name}",
            _tool_endpoint(spec),
            methods=["POST"],
            name=spec.name,
            operation_id=spec.name,
            summary=spec.title,
            description=spec.description,
            tags=["tools"],
            response_model=None,
        )


def _register_health(app: FastAPI) -> None:
    @app.get("/health", tags=["system"])
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "praxis",
            "version": API_VERSION,
            "tools": len(registry),
        }


def create_app() -> FastAPI:
    mcp_server = build_mcp_server()
    mcp_app = mcp_server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        host="0.0.0.0",
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(
        title="PRAXIS",
        version=API_VERSION,
        description=(
            "Backend determinista de herramientas para agentes de IA. "
            "Cada tool devuelve un sobre JSON con datos y metadatos."
        ),
        lifespan=lifespan,
    )
    _register_tool_routes(app)
    _register_health(app)
    app.mount("/", mcp_app)
    app.state.mcp = mcp_server
    return app


app = create_app()
