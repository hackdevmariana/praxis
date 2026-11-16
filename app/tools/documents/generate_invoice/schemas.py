from datetime import date as Date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class InvoiceDocumentType(StrEnum):
    invoice = "invoice"
    delivery_note = "delivery_note"


class ClientInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cif: str | None = Field(default=None, max_length=20)
    vat_number: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    postal_code: str | None = Field(default=None, max_length=10)
    municipality: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    country: str = Field(default="ES", min_length=2, max_length=2)
    email: str | None = Field(default=None, max_length=254)

    @field_validator("country")
    @classmethod
    def uppercase_country(cls, value: str) -> str:
        return value.upper()


class LineInput(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, decimal_places=3)
    unit_price: Decimal = Field(ge=0, decimal_places=4)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)


class GenerateInvoiceInput(BaseModel):
    client: ClientInput
    lines: list[LineInput] = Field(min_length=1, max_length=200)
    number: str | None = Field(default=None, pattern=r"^[A-Za-z0-9/-]{1,30}$")
    series: str | None = Field(default=None, max_length=10)
    date: Date
    due_date: Date | None = None
    vat_rate: Decimal = Field(default=Decimal("21"), ge=0, le=100)
    document_type: InvoiceDocumentType = InvoiceDocumentType.invoice
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=2000)
    payment_terms: str | None = Field(default=None, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def validate_due_date(self) -> "GenerateInvoiceInput":
        if self.due_date is not None and self.due_date < self.date:
            raise ValueError("due_date no puede ser anterior a date")
        return self

    @model_validator(mode="after")
    def validate_tax_id(self) -> "GenerateInvoiceInput":
        if self.document_type is not InvoiceDocumentType.invoice:
            return self
        if self.client.country == "ES":
            if not self.client.cif:
                raise ValueError("El CIF es obligatorio para facturas a clientes españoles")
        elif not self.client.vat_number:
            raise ValueError("El VAT number es obligatorio para facturas a clientes extranjeros")
        return self


class GenerateInvoiceOutput(BaseModel):
    document_id: str
    invoice_id: str
    pdf_path: str
    number: str
    date: Date
    due_date: Date
    base: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    document_type: InvoiceDocumentType
    deduplicated: bool
