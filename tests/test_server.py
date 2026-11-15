import asyncio
import json
from typing import Any

from fastapi.testclient import TestClient
from mcp.client._memory import InMemoryTransport  # pyright: ignore[reportPrivateImportUsage]
from mcp.client.session import ClientSession
from mcp.types import TextContent

from app.main import create_app
from app.registry import registry


def test_health_and_tool_catalog() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/health")
        schema = client.get("/openapi.json").json()

    assert health.status_code == 200
    assert health.json()["tools"] == len(registry)
    for name in registry.names():
        assert f"/api/tools/{name}" in schema["paths"]


def test_rest_tool_returns_envelope() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/tools/finance.vat",
            json={"amount": "1000.00"},
            headers={"x-request-id": "req-rest"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["tool"] == "finance.vat"
    assert body["data"]["total_amount"] == "1210.00"
    assert body["metadata"]["warnings"] == []


def test_rest_validation_error_returns_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/tools/finance.vat", json={"amount": "-1"})

    assert response.status_code == 422


def test_rest_tool_error_is_structured() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/tools/finance.discounts",
            json={"amount": "50", "discounts": ["100"], "operation": "reverse"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["metadata"]["errors"][0]["code"] == "invalid_params"


def test_mcp_lists_and_calls_finance_vat() -> None:
    async def scenario() -> tuple[list[str], dict[str, Any], bool]:
        server = create_app().state.mcp
        async with (
            InMemoryTransport(server) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            result = await session.call_tool("finance.vat", {"amount": "1000.00"})
            item = result.content[0]
            assert isinstance(item, TextContent)
            return (
                [tool.name for tool in listed.tools],
                json.loads(item.text),
                bool(result.is_error),
            )

    names, envelope, is_error = asyncio.run(scenario())

    assert names == list(registry.names())
    assert is_error is False
    assert envelope["success"] is True
    assert envelope["tool"] == "finance.vat"
    assert envelope["data"]["vat_amount"] == "210.00"
    assert envelope["metadata"]["source"] == "deterministic"


def test_mcp_invalid_params_returns_structured_error() -> None:
    async def scenario() -> dict[str, Any]:
        server = create_app().state.mcp
        async with (
            InMemoryTransport(server) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                "finance.discounts",
                {"amount": "100", "discounts": ["100"], "operation": "reverse"},
            )
            item = result.content[0]
            assert isinstance(item, TextContent)
            return json.loads(item.text)

    envelope = asyncio.run(scenario())

    assert envelope["success"] is False
    assert envelope["metadata"]["errors"][0]["code"] == "invalid_params"


def test_mcp_endpoint_accepts_initialize() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0"},
                },
            },
            headers={"accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 200
    assert '"serverInfo"' in response.text
    assert '"name":"PRAXIS"' in response.text
