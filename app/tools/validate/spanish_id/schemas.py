from enum import StrEnum

from pydantic import BaseModel, Field


class IdType(StrEnum):
    auto = "auto"
    nif = "nif"
    nie = "nie"
    cif = "cif"


class SpanishIdInput(BaseModel):
    value: str = Field(min_length=1, max_length=20)
    type: IdType = IdType.auto


class SpanishIdOutput(BaseModel):
    valid: bool
    id_type: IdType
    normalized: str
    checksum_ok: bool
    reason: str | None = None
    warning: str | None = (
        "Un identificador válido no implica que la empresa o persona exista o esté activa."
    )
