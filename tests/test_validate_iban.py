import asyncio

from app.context import ToolContext
from app.tools.validate.iban.schemas import IbanInput, IbanOutput
from app.tools.validate.iban.tool import iban

CTX = ToolContext(request_id="test")


def validate(iban_value: str, bic: str | None = None) -> IbanOutput:
    result = asyncio.run(iban(IbanInput(iban=iban_value, bic=bic), CTX))
    return result.data


def test_valid_iban_golden() -> None:
    output = validate("ES9121000418450200051332")

    assert output.valid is True
    assert output.normalized == "ES9121000418450200051332"
    assert output.country == "ES"
    assert output.bban == "21000418450200051332"
    assert output.bic_valid is None
    assert output.reason is None


def test_spaces_and_lowercase_are_normalized() -> None:
    output = validate("es91 2100 0418 4502 0005 1332", "caixesbbxxx")

    assert output.valid is True
    assert output.normalized == "ES9121000418450200051332"
    assert output.bic_valid is True


def test_invalid_checksum() -> None:
    output = validate("ES9121000418450200051333")

    assert output.valid is False
    assert output.reason == "invalid_checksum"
    assert output.bban is None


def test_invalid_length_keeps_bic_result() -> None:
    output = validate("ES912100041845020005133", "CAIX1SBB")

    assert output.valid is False
    assert output.country == "ES"
    assert output.reason == "invalid_length"
    assert output.bic_valid is False


def test_unknown_country() -> None:
    output = validate("ZZ9121000418450200051332")

    assert output.valid is False
    assert output.country == "ZZ"
    assert output.reason == "unknown_country"


def test_bic_with_wrong_country_invalidates_iban() -> None:
    output = validate("ES9121000418450200051332", "BNPAFRPPXXX")

    assert output.valid is False
    assert output.bic_valid is True
    assert output.reason == "bic_country_mismatch"


def test_invalid_bic_does_not_invalidate_iban() -> None:
    output = validate("ES9121000418450200051332", "CAIX1SBB")

    assert output.valid is True
    assert output.bic_valid is False
    assert output.reason is None


def test_spanish_ccc_is_validated() -> None:
    output = validate("ES6421000418450200051333")

    assert output.valid is False
    assert output.reason == "invalid_checksum"
    assert output.bban is None


def test_result_type_is_validation() -> None:
    result = asyncio.run(iban(IbanInput(iban="ES9121000418450200051332"), CTX))

    assert result.metadata_extra["result_type"] == "validation"
