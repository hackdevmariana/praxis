from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class DocumentFormat(StrEnum):
    md = "md"
    pdf = "pdf"


class Criterion(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    weight_pct: Decimal = Field(ge=0, le=100)


class SupplierRef(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None


class RfpInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    scope_description: str = Field(min_length=1, max_length=5000)
    requirements: list[str] = Field(min_length=1, max_length=100)
    evaluation_criteria: list[Criterion] = Field(min_length=1, max_length=20)
    deadline: date
    budget_max: Decimal | None = Field(default=None, ge=0)
    contact_email: EmailStr
    suppliers: list[SupplierRef] = Field(default_factory=list[SupplierRef], max_length=50)
    document_format: DocumentFormat = DocumentFormat.md
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("evaluation_criteria")
    @classmethod
    def criterios_unicos(cls, value: list[Criterion]) -> list[Criterion]:
        if len({criterion.name for criterion in value}) != len(value):
            raise ValueError("Los criterios deben tener nombres únicos")
        return value

    @model_validator(mode="after")
    def pesos(self) -> "RfpInput":
        if abs(
            sum(item.weight_pct for item in self.evaluation_criteria) - Decimal("100")
        ) > Decimal("0.01"):
            raise ValueError("Los pesos de los criterios deben sumar 100")
        return self


class RfpOutput(BaseModel):
    document_id: str
    path: str
    title: str
    deadline: date
    criteria_count: int
    suppliers_count: int
    format: DocumentFormat
    checksum_sha256: str
    deduplicated: bool
