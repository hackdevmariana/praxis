from datetime import date as Date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    invoice = "invoice"
    delivery_note = "delivery_note"
    budget = "budget"


class ExtractInvoiceInput(BaseModel):
    document_id: UUID
    document_type: DocumentType = DocumentType.invoice
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")


class InvoiceLine(BaseModel):
    description: str
    quantity: Decimal | None
    unit_price: Decimal | None
    vat_rate: Decimal | None
    line_total: Decimal | None


class ExtractInvoiceOutput(BaseModel):
    issuer: str | None
    issuer_cif: str | None
    number: str | None
    date: Date | None
    due_date: Date | None
    lines: list[InvoiceLine]
    base: Decimal | None
    vat: Decimal | None
    total: Decimal | None
    currency: str | None
    needs_review: bool
    confidence: float
