import asyncio

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.tools.validate.email_phone.schemas import EmailPhoneInput, EmailPhoneOutput
from app.tools.validate.email_phone.tool import email_phone

CTX = ToolContext(request_id="test")


def validate(**kwargs: str) -> EmailPhoneOutput:
    result = asyncio.run(email_phone(EmailPhoneInput(**kwargs), CTX))
    return result.data


def test_email_and_mobile_golden() -> None:
    output = validate(email="ceo@empresa.es", phone="+34 612 345 678")

    assert output.email_valid is True
    assert output.email_normalized == "ceo@empresa.es"
    assert output.phone_valid is True
    assert output.phone_e164 == "+34612345678"
    assert output.phone_international == "+34 612 34 56 78"
    assert output.phone_type == "mobile"
    assert output.phone_country == "ES"
    assert output.phone_reason is None


def test_email_only() -> None:
    output = validate(email="a@b.es")

    assert output.email_valid is True
    assert output.phone_valid is None


def test_email_with_spaces_is_normalized() -> None:
    output = validate(email=" usuario@empresa.es ")

    assert output.email_valid is True
    assert output.email_normalized == "usuario@empresa.es"


def test_invalid_email() -> None:
    output = validate(email="usuario@")

    assert output.email_valid is False
    assert output.email_normalized is None
    assert output.email_reason == "invalid_format"


def test_fixed_phone_and_international_phone() -> None:
    fixed = validate(phone="915 55 55 55", default_region="ES")
    international = validate(phone="+33 1 42 68 53 00", default_region="ES")

    assert fixed.phone_e164 == "+34915555555"
    assert fixed.phone_international == "+34 915 55 55 55"
    assert fixed.phone_type == "fixed_line"
    assert international.phone_e164 == "+33142685300"
    assert international.phone_type == "fixed_line"
    assert international.phone_country == "FR"


def test_short_phone_is_invalid_length() -> None:
    output = validate(phone="123")

    assert output.phone_valid is False
    assert output.phone_reason == "invalid_length"


def test_no_contact_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        EmailPhoneInput()
