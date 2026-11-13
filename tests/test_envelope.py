import json
from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.envelope import Envelope, ResponseMetadata


class VatData(BaseModel):
    base_amount: Decimal
    total_amount: Decimal


def build_metadata() -> ResponseMetadata:
    return ResponseMetadata.model_validate(
        {
            "source": "deterministic",
            "source_type": "deterministic",
            "retrieved_at": datetime(2026, 11, 12, 12, 0, tzinfo=UTC),
            "result_type": "calculation",
            "currency": "EUR",
            "exchange_rate": Decimal("0.9200"),
            "next_review": date(2027, 1, 1),
        }
    )


def test_envelope_serializes_decimal_and_dates_as_strings() -> None:
    envelope = Envelope(
        success=True,
        tool="finance.vat",
        tool_version="1.0.0",
        data=VatData(base_amount=Decimal("1000.00"), total_amount=Decimal("1210.00")),
        metadata=build_metadata(),
    )

    payload = envelope.to_dict()

    assert payload["data"] == {
        "base_amount": "1000.00",
        "total_amount": "1210.00",
    }
    assert payload["metadata"]["retrieved_at"] == "2026-11-12T12:00:00+00:00"
    assert payload["metadata"]["valid_until"] is None
    assert payload["metadata"]["confidence"] is None
    assert payload["metadata"]["currency"] == "EUR"
    assert payload["metadata"]["exchange_rate"] == "0.9200"
    assert payload["metadata"]["next_review"] == "2027-01-01"
    assert "summary" not in payload


def test_envelope_includes_summary_when_present() -> None:
    envelope = Envelope(
        success=True,
        tool="finance.vat",
        tool_version="1.0.0",
        data={"total_amount": Decimal("1210.00")},
        metadata=build_metadata(),
        summary="Total: 1.210,00 €.",
    )

    payload = envelope.to_dict()

    assert payload["summary"] == "Total: 1.210,00 €."
    assert payload["data"]["total_amount"] == "1210.00"


def test_envelope_is_json_serializable() -> None:
    envelope = Envelope(
        success=True,
        tool="finance.vat",
        tool_version="1.0.0",
        data=VatData(base_amount=Decimal("1000.00"), total_amount=Decimal("1210.00")),
        metadata=build_metadata(),
    )

    assert json.loads(json.dumps(envelope.to_dict()))["success"] is True
