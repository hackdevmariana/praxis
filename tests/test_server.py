import asyncio
import json
from typing import Any

from fastapi.testclient import TestClient
from mcp.client._memory import InMemoryTransport  # pyright: ignore[reportPrivateImportUsage]
from mcp.client.session import ClientSession
from mcp.types import TextContent

from app.auth import (
    ApiKeyRecord,
    AuthSettings,
    InMemoryApiKeyStore,
    hash_api_key,
    issue_access_token,
)
from app.main import create_app
from app.registry import registry
from app.tenancy import InMemoryToolAccessPolicy, TenantProfile

COMPANY = "11111111-1111-4111-8111-111111111111"
AUTH_SETTINGS = AuthSettings(
    required=True,
    jwt_secret="test-secret-with-at-least-32-characters",
)


def test_health_and_tool_catalog() -> None:
    with TestClient(create_app(AuthSettings())) as client:
        health = client.get("/health")
        schema = client.get("/openapi.json").json()

    assert health.status_code == 200
    assert health.json()["tools"] == len(registry)
    for name in registry.names():
        assert f"/api/tools/{name}" in schema["paths"]


def test_rest_tool_returns_envelope() -> None:
    with TestClient(create_app(AuthSettings())) as client:
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


def test_rest_v2_finance_tool_returns_envelope() -> None:
    with TestClient(create_app(AuthSettings())) as client:
        response = client.post(
            "/api/tools/finance.business_kpi",
            json={"revenue": "1000", "cogs": "600", "operating_expenses": "250"},
            headers={"x-request-id": "req-v2-finance"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["tool"] == "finance.business_kpi"
    assert body["data"]["gross_profit"] == "400.00"
    assert body["metadata"]["source"] == "user_input"
    assert body["metadata"]["legal_disclaimer_required"] is True


def test_rest_validation_error_returns_422() -> None:
    with TestClient(create_app(AuthSettings())) as client:
        response = client.post("/api/tools/finance.vat", json={"amount": "-1"})

    assert response.status_code == 422


def test_rest_tool_error_is_structured() -> None:
    with TestClient(create_app(AuthSettings())) as client:
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
        server = create_app(AuthSettings()).state.mcp
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
        server = create_app(AuthSettings()).state.mcp
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
    with TestClient(create_app(AuthSettings())) as client:
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


def _token(scopes: list[str]) -> str:
    return issue_access_token(
        subject="user-1",
        company_id=COMPANY,
        role="admin",
        scopes=scopes,
        settings=AUTH_SETTINGS,
    )


def _authorization(scopes: list[str], *, confirm: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {_token(scopes)}"}
    if confirm:
        headers["X-PRAXIS-Confirm"] = "true"
    return headers


def test_rest_requires_authentication() -> None:
    with TestClient(create_app(AUTH_SETTINGS)) as client:
        response = client.post("/api/tools/finance.vat", json={"amount": "1000.00"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_rest_accepts_jwt_with_scope() -> None:
    with TestClient(create_app(AUTH_SETTINGS)) as client:
        response = client.post(
            "/api/tools/finance.vat",
            json={"amount": "1000.00"},
            headers=_authorization(["finance.calculate"]),
        )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_rest_rejects_missing_scope() -> None:
    with TestClient(create_app(AUTH_SETTINGS)) as client:
        response = client.post(
            "/api/tools/finance.vat",
            json={"amount": "1000.00"},
            headers=_authorization(["documents.read"]),
        )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is False
    assert body["metadata"]["errors"][0]["code"] == "permission_denied"
    assert body["metadata"]["errors"][0]["details"]["missing"] == ["finance.calculate"]


def test_rest_accepts_api_key() -> None:
    raw_key = "key-1.praxis-live-key-123"
    store = InMemoryApiKeyStore(
        [
            ApiKeyRecord(
                key_id="key-1",
                key_hash=hash_api_key(raw_key),
                user_id="user-2",
                company_id=COMPANY,
                role="manager",
                scopes=frozenset({"finance.calculate"}),
            )
        ]
    )

    with TestClient(create_app(AUTH_SETTINGS, store)) as client:
        response = client.post(
            "/api/tools/finance.vat",
            json={"amount": "1000.00"},
            headers={"X-API-Key": raw_key},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_effect_tool_requires_confirmation() -> None:
    body = {
        "title": "Visita comercial",
        "start": "2026-11-20T10:00:00+01:00",
        "end": "2026-11-20T11:00:00+01:00",
        "idempotency_key": "visita-2026-11-20",
    }
    with TestClient(create_app(AUTH_SETTINGS)) as client:
        response = client.post(
            "/api/tools/calendar.create_event",
            json=body,
            headers=_authorization(["calendar.write"]),
        )

    envelope = response.json()
    assert response.status_code == 200
    assert envelope["success"] is False
    assert envelope["metadata"]["errors"][0]["code"] == "confirmation_required"


def test_effect_tool_with_confirmation_reaches_connector() -> None:
    body = {
        "title": "Visita comercial",
        "start": "2026-11-20T10:00:00+01:00",
        "end": "2026-11-20T11:00:00+01:00",
        "idempotency_key": "visita-2026-11-20",
    }
    with TestClient(create_app(AUTH_SETTINGS)) as client:
        response = client.post(
            "/api/tools/calendar.create_event",
            json=body,
            headers=_authorization(["calendar.write"], confirm=True),
        )

    envelope = response.json()
    assert response.status_code == 200
    assert envelope["success"] is False
    assert envelope["metadata"]["errors"][0]["code"] == "connector_not_connected"


def test_mcp_endpoint_requires_authentication() -> None:
    with TestClient(create_app(AUTH_SETTINGS)) as client:
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

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_mcp_endpoint_accepts_jwt() -> None:
    with TestClient(create_app(AUTH_SETTINGS)) as client:
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
            headers={
                "accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {_token(['finance.calculate'])}",
            },
        )

    assert response.status_code == 200
    assert '"serverInfo"' in response.text


def _mcp_tool_payload(response_text: str) -> dict[str, Any]:
    for line in response_text.splitlines():
        if line.startswith("data: "):
            message = json.loads(line.removeprefix("data: "))
            item = message["result"]["content"][0]
            return json.loads(item["text"])
    raise AssertionError("No se encontró el sobre MCP")


def test_mcp_tool_call_uses_authenticated_context() -> None:
    with TestClient(create_app(AUTH_SETTINGS)) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "finance.vat",
                    "arguments": {"amount": "1000.00"},
                },
            },
            headers={
                "accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {_token(['finance.calculate'])}",
            },
        )

    envelope = _mcp_tool_payload(response.text)
    assert response.status_code == 200
    assert envelope["success"] is True
    assert envelope["data"]["total_amount"] == "1210.00"


def test_mcp_tool_call_rejects_missing_scope() -> None:
    with TestClient(create_app(AUTH_SETTINGS)) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "finance.vat",
                    "arguments": {"amount": "1000.00"},
                },
            },
            headers={
                "accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {_token(['documents.read'])}",
            },
        )

    envelope = _mcp_tool_payload(response.text)
    assert response.status_code == 200
    assert envelope["success"] is False
    assert envelope["metadata"]["errors"][0]["code"] == "permission_denied"


def _tenant_policy(
    *,
    catalog_key: str = "hotel",
    enabled_tools: frozenset[str] | None = None,
) -> InMemoryToolAccessPolicy:
    return InMemoryToolAccessPolicy(
        {
            COMPANY: TenantProfile(
                company_id=COMPANY,
                catalog_key=catalog_key,
                enabled_tools=enabled_tools,
            )
        }
    )


def _mcp_result_payload(response_text: str) -> dict[str, Any]:
    for line in response_text.splitlines():
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))["result"]
    return json.loads(response_text)["result"]


def test_mcp_list_filters_tenant_catalog() -> None:
    app = create_app(AUTH_SETTINGS, tool_access_policy=_tenant_policy())

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}},
            headers={
                "accept": "application/json, text/event-stream",
                **_authorization(["finance.calculate"]),
            },
        )

    names = [tool["name"] for tool in _mcp_result_payload(response.text)["tools"]]
    assert "finance.vat" in names
    assert "calendar.create_event" in names
    assert "procurement.tpv_savings" not in names
    assert "procurement.compare_offers" not in names


def test_rest_rejects_tool_outside_tenant_catalog() -> None:
    app = create_app(AUTH_SETTINGS, tool_access_policy=_tenant_policy())

    with TestClient(app) as client:
        response = client.post(
            "/api/tools/procurement.tpv_savings",
            json={
                "annual_card_turnover": "120000",
                "current_rate_pct": "1.5",
                "new_rate_pct": "1.0",
            },
            headers=_authorization(["procurement.calculate"]),
        )

    envelope = response.json()
    assert response.status_code == 200
    assert envelope["success"] is False
    assert envelope["metadata"]["errors"][0]["code"] == "tool_not_available"


def test_rest_rejects_deactivated_tool() -> None:
    app = create_app(
        AUTH_SETTINGS,
        tool_access_policy=_tenant_policy(enabled_tools=frozenset()),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/tools/finance.vat",
            json={"amount": "1000.00"},
            headers=_authorization(["finance.calculate"]),
        )

    envelope = response.json()
    assert response.status_code == 200
    assert envelope["success"] is False
    assert envelope["metadata"]["errors"][0]["code"] == "tool_not_available"


def test_mcp_rejects_tool_outside_tenant_catalog() -> None:
    app = create_app(AUTH_SETTINGS, tool_access_policy=_tenant_policy())

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "procurement.tpv_savings",
                    "arguments": {
                        "annual_card_turnover": "120000",
                        "current_rate_pct": "1.5",
                        "new_rate_pct": "1.0",
                    },
                },
            },
            headers={
                "accept": "application/json, text/event-stream",
                **_authorization(["procurement.calculate"]),
            },
        )

    envelope = _mcp_tool_payload(response.text)
    assert envelope["success"] is False
    assert envelope["metadata"]["errors"][0]["code"] == "tool_not_available"


def test_mcp_missing_tenant_profile_hides_all_tools() -> None:
    app = create_app(
        AUTH_SETTINGS,
        tool_access_policy=InMemoryToolAccessPolicy(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 12, "method": "tools/list", "params": {}},
            headers={
                "accept": "application/json, text/event-stream",
                **_authorization(["finance.calculate"]),
            },
        )

    assert _mcp_result_payload(response.text)["tools"] == []
