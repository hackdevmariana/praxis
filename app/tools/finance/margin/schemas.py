from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class MarginInput(BaseModel):
    cost: Decimal | None = Field(default=None, max_digits=16, decimal_places=2)
    price: Decimal | None = Field(default=None, max_digits=16, decimal_places=2)
    margin_pct: Decimal | None = Field(default=None, lt=100)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    @model_validator(mode="after")
    def exactly_two(self) -> "MarginInput":
        given = sum(value is not None for value in (self.cost, self.price, self.margin_pct))
        if given != 2:
            raise ValueError("Aporta exactamente dos de {cost, price, margin_pct}")
        return self


class MarginOutput(BaseModel):
    cost: Decimal | None
    price: Decimal | None
    margin_amount: Decimal
    margin_pct: Decimal | None
    markup_pct: Decimal | None
    currency: str
