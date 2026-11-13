import pytest

from app.errors import ErrorCode, ToolError


def test_error_code_serializes_as_plain_string() -> None:
    error = ToolError(ErrorCode.INVALID_PARAMS, "Importe inválido")

    assert error.code == "invalid_params"
    assert str(error) == "Importe inválido"
    assert error.to_dict() == {
        "code": "invalid_params",
        "message": "Importe inválido",
    }


def test_tool_error_accepts_domain_codes_and_details() -> None:
    error = ToolError("incompatible_units", "Dimensiones distintas", details={"from": "kg"})

    assert error.code == "incompatible_units"
    assert error.to_dict()["details"] == {"from": "kg"}


def test_tool_error_is_an_exception() -> None:
    with pytest.raises(ToolError, match="boom"):
        raise ToolError("internal_error", "boom")
