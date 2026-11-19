"""FastAPI application and MCP server for the PRAXIS tool catalog."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from inspect import Parameter, Signature
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app import tools
from app.audit import (
    ExecutionLogStore,
    NoopExecutionLogStore,
    SqlAlchemyExecutionLogStore,
    set_execution_log_store,
)
from app.auth import (
    ApiKeyStore,
    AuthMiddleware,
    AuthSettings,
    current_context,
    fallback_context,
    load_api_key_store,
)
from app.db.engine import create_db_engine
from app.db.idempotency import SqlAlchemyIdempotencyStore
from app.errors import ToolError
from app.execution import error_envelope, execute_tool
from app.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
    set_idempotency_store,
)
from app.mcp_server import build_mcp_server
from app.providers.adapters import configure_adapters
from app.registry import ToolSpec, registry
from app.tenancy import (
    AllowAllToolAccess,
    SqlAlchemyToolAccessPolicy,
    ToolAccessPolicy,
    apply_tool_access,
)

API_VERSION = "0.1.0"
_TOOL_MODULES = tools  # imported for registration side effects
logger = logging.getLogger(__name__)


def _tool_endpoint(
    spec: ToolSpec,
    settings: AuthSettings,
    tool_access_policy: ToolAccessPolicy,
) -> Callable[..., Any]:
    async def endpoint(**kwargs: Any) -> dict[str, Any]:
        request = cast(Request, kwargs["request"])
        params = cast(BaseModel, kwargs["params"])
        request_id = request.headers.get("x-request-id") or uuid4().hex
        try:
            ctx = current_context()
            if ctx is None:
                ctx = await apply_tool_access(
                    fallback_context(
                        settings,
                        request_id=request_id,
                        channel="http",
                    ),
                    tool_access_policy,
                )
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


def _register_tool_routes(
    app: FastAPI,
    settings: AuthSettings,
    tool_access_policy: ToolAccessPolicy,
) -> None:
    for spec in registry.all():
        app.add_api_route(
            f"/api/tools/{spec.name}",
            _tool_endpoint(spec, settings, tool_access_policy),
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


def create_app(
    settings: AuthSettings | None = None,
    api_key_store: ApiKeyStore | None = None,
    tool_access_policy: ToolAccessPolicy | None = None,
    execution_log_store: ExecutionLogStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
    database_url: str | None = None,
) -> FastAPI:
    auth_settings = settings or AuthSettings.from_env()
    keys = api_key_store or load_api_key_store(auth_settings)
    engine = create_db_engine(database_url)
    configure_adapters(engine)

    if tool_access_policy is not None:
        access_policy = tool_access_policy
    elif engine is not None:
        access_policy = SqlAlchemyToolAccessPolicy(engine)
    else:
        access_policy = AllowAllToolAccess()

    if execution_log_store is not None:
        audit_store = execution_log_store
    elif engine is not None:
        audit_store = SqlAlchemyExecutionLogStore(engine)
    else:
        audit_store = NoopExecutionLogStore()

    if idempotency_store is not None:
        idem_store = idempotency_store
    elif engine is not None:
        idem_store = SqlAlchemyIdempotencyStore(engine)
    else:
        idem_store = InMemoryIdempotencyStore()

    set_execution_log_store(audit_store)
    set_idempotency_store(idem_store)
    if not auth_settings.required:
        logger.warning("PRAXIS_AUTH_REQUIRED=false: contexto de desarrollo con scope '*'")
    mcp_server = build_mcp_server(auth_settings, access_policy)
    mcp_app = mcp_server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        host="0.0.0.0",
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(
        title="PRAXIS",
        version=API_VERSION,
        description=(
            "Backend determinista de herramientas para agentes de IA. "
            "Cada tool devuelve un sobre JSON con datos y metadatos."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        AuthMiddleware,
        settings=auth_settings,
        api_key_store=keys,
        tool_access_policy=access_policy,
    )
    _register_tool_routes(app, auth_settings, access_policy)
    _register_health(app)
    app.mount("/", mcp_app)
    app.state.mcp = mcp_server
    app.state.auth_settings = auth_settings
    app.state.tool_access_policy = access_policy
    app.state.execution_log_store = audit_store
    app.state.idempotency_store = idem_store
    app.state.engine = engine
    return app


app = create_app()
