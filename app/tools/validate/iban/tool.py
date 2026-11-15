import re

import stdnum.iban
from stdnum.exceptions import InvalidChecksum, InvalidComponent, InvalidFormat, InvalidLength

from app.context import ToolContext
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.validate.iban.schemas import IbanInput, IbanOutput

_BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")
_BBAN_TOKEN_RE = re.compile(r"(\d+)!")
_IBAN_DB = stdnum.iban.numdb.get("iban")  # pyright: ignore[reportPrivateImportUsage]


def _normalize(value: str) -> str:
    return value.replace(" ", "").upper()


def _expected_length(country: str) -> int | None:
    info = _IBAN_DB.info(country)
    if not info:
        return None
    bban = info[0][1].get("bban")
    if bban is None:
        return None
    return 4 + sum(int(size) for size in _BBAN_TOKEN_RE.findall(bban))


def _bic_valid(bic: str | None) -> bool | None:
    if bic is None:
        return None
    return _BIC_RE.fullmatch(_normalize(bic)) is not None


@tool(
    name="validate.iban",
    version="1.0.0",
    title="Validar IBAN y BIC",
    permissions=["validation.check"],
    data_classification="personal",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Valida la estructura y los dígitos de control de un IBAN y, opcionalmente, "
        "un BIC/SWIFT. No confirma que la cuenta exista ni que esté operativa. "
        "No usar para validar tarjetas ni números de cuenta sin IBAN."
    ),
)
async def iban(params: IbanInput, ctx: ToolContext) -> ToolResult[IbanOutput]:
    normalized = _normalize(params.iban)
    country = normalized[:2] if len(normalized) >= 2 and normalized[:2].isalpha() else None
    bic_valid = _bic_valid(params.bic)
    bic_country = _normalize(params.bic)[4:6] if bic_valid and params.bic else None

    reason: str | None = None
    expected_length = _expected_length(country) if country else None

    if country is None:
        reason = "invalid_length" if len(normalized) < 4 else "invalid_format"
    elif expected_length is None:
        reason = "unknown_country"
    elif len(normalized) != expected_length:
        reason = "invalid_length"
    else:
        try:
            stdnum.iban.validate(normalized)
        except InvalidChecksum:
            reason = "invalid_checksum"
        except InvalidLength:
            reason = "invalid_length"
        except (InvalidFormat, InvalidComponent):
            reason = "invalid_format"

    if reason is None and bic_country is not None and bic_country != country:
        reason = "bic_country_mismatch"

    valid = reason is None
    return tool_result(
        IbanOutput(
            valid=valid,
            normalized=normalized,
            country=country,
            bban=normalized[4:] if valid else None,
            bic_valid=bic_valid,
            reason=reason,
        ),
        metadata_extra={"result_type": "validation"},
    )
