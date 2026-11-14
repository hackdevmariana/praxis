import re

import stdnum.es.cif as cif

from app.context import ToolContext
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.validate.spanish_id.schemas import IdType, SpanishIdInput, SpanishIdOutput

_CONTROL = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIF_RE = re.compile(r"^\d{8}[A-Z]$")
_NIE_RE = re.compile(r"^[XYZ]\d{7}[A-Z]$")
_CIF_RE = re.compile(r"^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$")
_SEPARATORS_RE = re.compile(r"[\s.\-]+")


def _normalize(value: str) -> str:
    return _SEPARATORS_RE.sub("", value).upper()


def _detect_type(normalized: str) -> IdType:
    if _NIE_RE.fullmatch(normalized):
        return IdType.nie
    if _NIF_RE.fullmatch(normalized):
        return IdType.nif
    if _CIF_RE.fullmatch(normalized):
        return IdType.cif
    first = normalized[:1]
    if first in {"X", "Y", "Z"}:
        return IdType.nie
    if first.isdigit():
        return IdType.nif
    return IdType.cif


def _nif_checksum_ok(normalized: str, id_type: IdType) -> bool:
    if id_type is IdType.nie:
        prefix = {"X": "0", "Y": "1", "Z": "2"}[normalized[0]]
        number = int(prefix + normalized[1:8])
    else:
        number = int(normalized[:8])
    return normalized[-1] == _CONTROL[number % 23]


def _pattern_for(id_type: IdType) -> re.Pattern[str] | None:
    return {
        IdType.nif: _NIF_RE,
        IdType.nie: _NIE_RE,
        IdType.cif: _CIF_RE,
    }.get(id_type)


@tool(
    name="validate.spanish_id",
    version="1.0.0",
    title="Validar NIF, NIE o CIF",
    permissions=["validation.check"],
    data_classification="personal",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Valida el formato y el dígito de control de un NIF, NIE o CIF español. "
        "No consulta registros ni confirma que la persona o empresa exista. "
        "No usar para validar números de la Seguridad Social ni identificadores de otros países."
    ),
)
async def spanish_id(params: SpanishIdInput, ctx: ToolContext) -> ToolResult[SpanishIdOutput]:
    normalized = _normalize(params.value)
    id_type = params.type if params.type is not IdType.auto else _detect_type(normalized)
    pattern = _pattern_for(id_type)

    if pattern is None or not pattern.fullmatch(normalized):
        reason = (
            "type_mismatch"
            if params.type is not IdType.auto
            else ("invalid_length" if len(normalized) != 9 else "invalid_format")
        )
        return tool_result(
            SpanishIdOutput(
                valid=False,
                id_type=id_type,
                normalized=normalized,
                checksum_ok=False,
                reason=reason,
            )
        )

    checksum_ok = (
        cif.is_valid(normalized) if id_type is IdType.cif else _nif_checksum_ok(normalized, id_type)
    )
    return tool_result(
        SpanishIdOutput(
            valid=checksum_ok,
            id_type=id_type,
            normalized=normalized,
            checksum_ok=checksum_ok,
            reason=None if checksum_ok else "invalid_checksum",
        )
    )
