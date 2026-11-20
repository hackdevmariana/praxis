from decimal import Decimal

from pydantic import BaseModel, Field


class PriceItem(BaseModel):
    supplier: str
    product_code: str | None = None
    description: str
    previous_unit_price: Decimal = Field(ge=0)
    current_unit_price: Decimal = Field(ge=0)
    previous_date: str | None = None
    current_date: str | None = None
    annual_quantity: Decimal | None = Field(default=None, ge=0)


class PriceIncreaseInput(BaseModel):
    items: list[PriceItem] = Field(min_length=1, max_length=500)
    threshold_pct: Decimal = Field(default=Decimal("10"), gt=0, le=100)


class PriceAlert(BaseModel):
    supplier: str
    product_code: str | None
    description: str
    previous_unit_price: Decimal
    current_unit_price: Decimal
    change_amount: Decimal
    change_pct: Decimal | None
    annual_impact: Decimal | None
    is_new_price: bool
    is_anomalous: bool
    severity: str


class PriceIncreaseOutput(BaseModel):
    alerts: list[PriceAlert]
    anomalous_count: int
    high_count: int
    medium_count: int
    new_price_count: int
    currency: str
