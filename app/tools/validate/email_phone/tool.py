from email_validator import EmailNotValidError, validate_email
from phonenumbers import (
    NumberParseException,
    PhoneNumberFormat,
    PhoneNumberType,
    format_number,
    is_possible_number_with_reason,
    is_valid_number,
    number_type,
    parse,
    region_code_for_number,
)
from phonenumbers.phonenumberutil import ValidationResult

from app.context import ToolContext
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.validate.email_phone.schemas import EmailPhoneInput, EmailPhoneOutput

_PHONE_TYPES = {
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE: "fixed_line",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_line",
    PhoneNumberType.VOIP: "voip",
    PhoneNumberType.TOLL_FREE: "toll_free",
}


def _invalid_phone_reason(error_type: int) -> str:
    if error_type in (NumberParseException.TOO_SHORT_NSN, NumberParseException.TOO_LONG):
        return "invalid_length"
    if error_type == NumberParseException.INVALID_COUNTRY_CODE:
        return "invalid_country"
    if error_type == NumberParseException.NOT_A_NUMBER:
        return "invalid_format"
    return "parse_error"


@tool(
    name="validate.email_phone",
    version="1.0.0",
    title="Validar email y teléfono",
    permissions=["validation.check"],
    data_classification="personal",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Valida el formato de un email y/o un teléfono y los normaliza. "
        "No comprueba la entrega del correo ni la titularidad del número. "
        "No usar para verificar identidad ni para consultar directorios."
    ),
)
async def email_phone(params: EmailPhoneInput, ctx: ToolContext) -> ToolResult[EmailPhoneOutput]:
    output = EmailPhoneOutput()

    if params.email is not None:
        try:
            validated = validate_email(params.email.strip(), check_deliverability=False)
        except EmailNotValidError:
            output.email_valid = False
            output.email_reason = "invalid_format"
        else:
            output.email_valid = True
            output.email_normalized = validated.normalized

    if params.phone is not None:
        try:
            number = parse(params.phone, params.default_region.upper())
        except NumberParseException as error:
            output.phone_valid = False
            output.phone_reason = _invalid_phone_reason(error.error_type)
        else:
            if is_valid_number(number):
                output.phone_valid = True
                output.phone_e164 = format_number(number, PhoneNumberFormat.E164)
                output.phone_international = format_number(number, PhoneNumberFormat.INTERNATIONAL)
                output.phone_type = _PHONE_TYPES.get(number_type(number), "unknown")
                output.phone_country = region_code_for_number(number)
            else:
                output.phone_valid = False
                possible_reason = is_possible_number_with_reason(number)
                output.phone_reason = (
                    "invalid_length"
                    if possible_reason in (ValidationResult.TOO_SHORT, ValidationResult.TOO_LONG)
                    else "invalid_format"
                )

    return tool_result(output, metadata_extra={"result_type": "validation"})
