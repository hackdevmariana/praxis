import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.audit import ExecutionLogRecord, InMemoryExecutionLogStore
from app.auth import AuthSettings, issue_access_token
from app.clock import MADRID
from app.main import create_app
from app.providers.contracts import ContractRecord, set_contract_repository
from app.providers.documents import StoredDocument, set_document_repository
from app.providers.google_calendar import (
    CalendarEventRecord,
    CalendarPage,
    CreatedEventRecord,
    set_calendar_connector,
)
from app.tenancy import InMemoryToolAccessPolicy, TenantProfile

HOTEL_COMPANY = "11111111-1111-4111-8111-111111111111"
CEO_COMPANY = "22222222-2222-4222-8222-222222222222"
ASSOCIATION_COMPANY = "33333333-3333-4333-8333-333333333333"
CONTRACT_ID = UUID("44444444-4444-4444-8444-444444444444")
DOCUMENT_ID = UUID("55555555-5555-4555-8555-555555555555")
FIXTURE_PDF = Path(__file__).parent / "fixtures" / "invoice-F-2026-0042.pdf"
AUTH_SETTINGS = AuthSettings(
    required=True,
    jwt_secret="test-secret-with-at-least-32-characters",
)


class RecordingCalendarConnector:
    def __init__(self) -> None:
        self.calendar_ids: list[str] = []

    async def list_events(
        self,
        *,
        calendar_id: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> CalendarPage:
        self.calendar_ids.append(calendar_id)
        return CalendarPage(
            events=(
                CalendarEventRecord(
                    id="evt_work_001",
                    title="Reunión de gerencia",
                    start="2026-11-20T09:00:00+01:00",
                    end="2026-11-20T10:00:00+01:00",
                    location="Sala Junta",
                    attendees=("ana@hotel.example",),
                    status="confirmed",
                    is_all_day=False,
                    html_link="https://calendar.example/evt_work_001",
                ),
            )
        )

    async def create_event(
        self,
        *,
        calendar_id: str,
        title: str,
        start: datetime,
        end: datetime,
        description: str | None,
        location: str | None,
        attendees: Sequence[str],
        all_day: bool,
        timezone: str,
        send_notifications: bool,
        recurrence_rrule: str | None,
    ) -> CreatedEventRecord:
        self.calendar_ids.append(calendar_id)
        return CreatedEventRecord(
            event_id="evt_created_001",
            html_link="https://calendar.example/evt_created_001",
            status="confirmed",
            start="2026-11-20T12:00:00+01:00",
            end="2026-11-20T13:00:00+01:00",
            created=datetime(2026, 11, 18, 10, 0, tzinfo=MADRID),
        )


class FixtureDocumentRepository:
    def __init__(self, company_id: str) -> None:
        self.company_id = company_id

    async def get(self, *, company_id: str, document_id: UUID) -> StoredDocument | None:
        if company_id != self.company_id or document_id != DOCUMENT_ID:
            return None
        return StoredDocument(
            document_id=document_id,
            company_id=company_id,
            filename="invoice-F-2026-0042.pdf",
            content=FIXTURE_PDF.read_bytes(),
        )


class FixedContractRepository:
    def __init__(self, company_id: str) -> None:
        self.company_id = company_id

    async def get(self, *, company_id: str, contract_id: UUID) -> ContractRecord | None:
        if company_id != self.company_id or contract_id != CONTRACT_ID:
            return None
        return ContractRecord(id=contract_id, company_id=company_id)


def _access_policy(company_id: str, catalog_key: str) -> InMemoryToolAccessPolicy:
    return InMemoryToolAccessPolicy(
        {
            company_id: TenantProfile(
                company_id=company_id,
                catalog_key=catalog_key,
            )
        }
    )


def _headers(
    company_id: str,
    scopes: Sequence[str],
    *,
    request_id: str,
    confirm: bool = False,
) -> dict[str, str]:
    token = issue_access_token(
        subject="scenario-user",
        company_id=company_id,
        role="admin",
        scopes=scopes,
        settings=AUTH_SETTINGS,
    )
    headers = {
        "accept": "application/json, text/event-stream",
        "authorization": f"Bearer {token}",
        "x-request-id": request_id,
    }
    if confirm:
        headers["x-praxis-confirm"] = "true"
    return headers


def _mcp_call(
    client: TestClient,
    name: str,
    arguments: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    assert response.status_code == 200
    for line in response.text.splitlines():
        if line.startswith("data: "):
            message = json.loads(line.removeprefix("data: "))
            item = message["result"]["content"][0]
            return json.loads(item["text"])
    raise AssertionError("No se encontró el sobre MCP")


def _mcp_logs(records: list[ExecutionLogRecord]) -> list[str]:
    assert all(record.channel == "mcp" for record in records)
    assert all(record.success for record in records)
    return [record.tool_name for record in records]


def test_scenario_hotel_agenda_and_confirmed_appointment() -> None:
    connector = RecordingCalendarConnector()
    set_calendar_connector(connector)
    store = InMemoryExecutionLogStore()
    app = create_app(
        AUTH_SETTINGS,
        tool_access_policy=_access_policy(HOTEL_COMPANY, "hotel"),
        execution_log_store=store,
    )

    with TestClient(app) as client:
        listed = _mcp_call(
            client,
            "calendar.list_events",
            {
                "start": "2026-11-20T00:00:00+01:00",
                "end": "2026-11-21T00:00:00+01:00",
                "calendar_id": "work",
            },
            _headers(
                HOTEL_COMPANY,
                ["calendar.read"],
                request_id="hotel-list",
            ),
        )
        created = _mcp_call(
            client,
            "calendar.create_event",
            {
                "title": "Visita del gerente",
                "start": "2026-11-20T12:00:00+01:00",
                "end": "2026-11-20T13:00:00+01:00",
                "calendar_id": "work",
                "idempotency_key": "cita-hotel-20261120",
            },
            _headers(
                HOTEL_COMPANY,
                ["calendar.write"],
                request_id="hotel-create",
                confirm=True,
            ),
        )

    assert listed["success"] is True
    assert [event["id"] for event in listed["data"]["events"]] == ["evt_work_001"]
    assert created["success"] is True
    assert created["data"]["event_id"] == "evt_created_001"
    assert connector.calendar_ids == ["work", "work"]
    assert _mcp_logs(store.records) == [
        "calendar.list_events",
        "calendar.create_event",
    ]
    assert [record.request_id for record in store.records] == [
        "hotel-list",
        "hotel-create",
    ]


def test_scenario_ceo_vat_invoice_extraction_and_offer_comparison() -> None:
    set_document_repository(FixtureDocumentRepository(CEO_COMPANY))
    store = InMemoryExecutionLogStore()
    app = create_app(
        AUTH_SETTINGS,
        tool_access_policy=_access_policy(CEO_COMPANY, "poligono"),
        execution_log_store=store,
    )
    scopes = ["finance.calculate", "documents.read", "procurement.calculate"]

    with TestClient(app) as client:
        vat = _mcp_call(
            client,
            "finance.vat",
            {"amount": "1000.00"},
            _headers(CEO_COMPANY, scopes, request_id="ceo-vat"),
        )
        extracted = _mcp_call(
            client,
            "documents.extract_invoice",
            {"document_id": str(DOCUMENT_ID), "document_type": "invoice"},
            _headers(CEO_COMPANY, scopes, request_id="ceo-extract"),
        )
        compared = _mcp_call(
            client,
            "procurement.compare_offers",
            {
                "offers": [
                    {
                        "supplier": "Proveedor A",
                        "monthly_price": "100.00",
                        "permanence_months": 12,
                        "cancellation_cost": "50.00",
                    },
                    {"supplier": "Proveedor B", "monthly_price": "110.00"},
                ],
                "years": 3,
                "normalize_by": "total_cost",
            },
            _headers(CEO_COMPANY, scopes, request_id="ceo-compare"),
        )

    assert vat["data"]["total_amount"] == "1210.00"
    assert extracted["data"]["issuer"] == "Suministros García S.L."
    assert extracted["data"]["total"] == "199.65"
    assert compared["data"]["ranking"][0]["supplier"] == "Proveedor A"
    assert len(compared["data"]["normalized_table"]) == 2
    assert _mcp_logs(store.records) == [
        "finance.vat",
        "documents.extract_invoice",
        "procurement.compare_offers",
    ]


def test_scenario_association_tpv_savings_and_renewal_alert() -> None:
    set_contract_repository(FixedContractRepository(ASSOCIATION_COMPANY))
    store = InMemoryExecutionLogStore()
    app = create_app(
        AUTH_SETTINGS,
        tool_access_policy=_access_policy(ASSOCIATION_COMPANY, "asociacion"),
        execution_log_store=store,
    )

    with TestClient(app) as client:
        savings = _mcp_call(
            client,
            "procurement.tpv_savings",
            {
                "annual_card_turnover": "120000.00",
                "current_rate_pct": "2.5",
                "new_rate_pct": "1.8",
            },
            _headers(
                ASSOCIATION_COMPANY,
                ["procurement.calculate"],
                request_id="association-savings",
            ),
        )
        alert = _mcp_call(
            client,
            "alerts.contract_renewal",
            {
                "contract_id": str(CONTRACT_ID),
                "renewal_date": "2030-03-31",
                "notice_days": [60, 30, 15],
                "channel": "none",
                "idempotency_key": "renovacion-asociacion-2030",
            },
            _headers(
                ASSOCIATION_COMPANY,
                ["alerts.write"],
                request_id="association-alert",
                confirm=True,
            ),
        )

    assert savings["data"]["annual_savings"] == "840.00"
    assert alert["success"] is True
    assert [entry["days_before"] for entry in alert["data"]["schedule"]] == [60, 30, 15]
    assert alert["data"]["next_trigger_at"] is not None
    assert _mcp_logs(store.records) == [
        "procurement.tpv_savings",
        "alerts.contract_renewal",
    ]
