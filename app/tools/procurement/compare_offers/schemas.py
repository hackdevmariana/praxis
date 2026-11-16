from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class NormalizeBy(StrEnum):
    total_cost = "total_cost"
    monthly = "monthly"
    annual = "annual"


class OfferInput(BaseModel):
    supplier: str = Field(min_length=1, max_length=120)
    monthly_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    permanence_months: int = Field(default=0, ge=0, le=120)
    cancellation_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    year2_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    year3_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    upfront_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    vat_included: bool = False
    vat_rate: Decimal = Field(default=Decimal("21"), ge=0, le=100)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class CompareOffersInput(BaseModel):
    offers: list[OfferInput] = Field(min_length=2, max_length=5)
    years: int = Field(default=5, ge=1, le=10)
    normalize_by: NormalizeBy = NormalizeBy.total_cost


class OfferRow(BaseModel):
    supplier: str
    monthly_price_net: Decimal
    recurring_cost: Decimal
    one_off_cost: Decimal
    total_cost: Decimal
    annual_cost: Decimal
    monthly_cost: Decimal
    permanence_months: int
    rank: int
    is_cheapest: bool
    savings_vs_most_expensive: Decimal


class CompareOffersOutput(BaseModel):
    years: int
    normalize_by: NormalizeBy
    currency: str
    ranking: list[dict[str, Any]]
    normalized_table: list[OfferRow]
