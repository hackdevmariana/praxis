from datetime import UTC, datetime

import time_machine

from app.metadata import build_metadata


@time_machine.travel(datetime(2026, 11, 13, 10, 0, tzinfo=UTC))
def test_build_metadata_defaults_to_madrid_now() -> None:
    metadata = build_metadata()

    assert metadata.source == "deterministic"
    assert metadata.source_type == "deterministic"
    assert metadata.retrieved_at.isoformat() == "2026-11-13T11:00:00+01:00"
    assert metadata.valid_until is None
    assert metadata.result_type == "calculation"
    assert metadata.is_estimated is False
    assert metadata.timezone == "Europe/Madrid"
    assert metadata.warnings == []
    assert metadata.errors == []
    assert metadata.legal_disclaimer_required is False


def test_build_metadata_accepts_external_sources_and_extras() -> None:
    retrieved = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
    metadata = build_metadata(
        source="bce",
        source_type="external_api",
        retrieved_at=retrieved,
        valid_until=datetime(2026, 11, 14, 9, 0, tzinfo=UTC),
        result_type="lookup",
        is_estimated=True,
        confidence=0.9,
        warnings=["fallback_used"],
        errors=[{"code": "stale_rate", "message": "Tipo de cambio antiguo"}],
        currency="EUR",
        rate_date="2026-11-13",
    )

    assert metadata.retrieved_at == retrieved
    assert metadata.is_estimated is True
    assert metadata.confidence == 0.9
    assert metadata.warnings == ["fallback_used"]
    assert metadata.errors[0]["code"] == "stale_rate"
    assert metadata.model_extra is not None
    assert metadata.model_extra["currency"] == "EUR"
    assert metadata.model_extra["rate_date"] == "2026-11-13"


def test_build_metadata_copies_mutable_inputs() -> None:
    warnings = ["first"]
    errors: list[dict[str, str]] = [{"code": "x"}]

    metadata = build_metadata(warnings=warnings, errors=errors)
    warnings.append("second")
    errors[0]["code"] = "changed"

    assert metadata.warnings == ["first"]
    assert metadata.errors == [{"code": "x"}]
