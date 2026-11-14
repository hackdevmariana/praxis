import asyncio

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.tools.validate.spanish_id.schemas import IdType, SpanishIdInput, SpanishIdOutput
from app.tools.validate.spanish_id.tool import spanish_id

CTX = ToolContext(request_id="test")


def validate(value: str, id_type: IdType = IdType.auto) -> SpanishIdOutput:
    result = asyncio.run(spanish_id(SpanishIdInput(value=value, type=id_type), CTX))
    return result.data


def test_valid_dni_and_normalization() -> None:
    assert validate("12345678Z") == validate("12.345.678-z")
    output = validate("12345678Z")

    assert output.valid is True
    assert output.id_type is IdType.nif
    assert output.normalized == "12345678Z"
    assert output.checksum_ok is True
    assert output.reason is None


def test_valid_nie() -> None:
    output = validate("X1234567L")

    assert output.valid is True
    assert output.id_type is IdType.nie
    assert output.checksum_ok is True


def test_valid_cif() -> None:
    output = validate("A58818501")

    assert output.valid is True
    assert output.id_type is IdType.cif
    assert output.checksum_ok is True


@pytest.mark.parametrize(
    ("value", "id_type", "reason"),
    [
        ("12345678A", IdType.auto, "invalid_checksum"),
        ("A58818500", IdType.auto, "invalid_checksum"),
        ("1234", IdType.auto, "invalid_length"),
        ("X1234567L", IdType.nif, "type_mismatch"),
        ("ABC", IdType.auto, "invalid_length"),
    ],
)
def test_invalid_identifiers(value: str, id_type: IdType, reason: str) -> None:
    output = validate(value, id_type)

    assert output.valid is False
    assert output.checksum_ok is False
    assert output.reason == reason


def test_empty_value_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        SpanishIdInput(value="")
