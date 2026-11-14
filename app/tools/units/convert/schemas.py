from decimal import Decimal

from pydantic import BaseModel, Field


class UnitsConvertInput(BaseModel):
    value: Decimal
    from_unit: str = Field(min_length=1, max_length=32)
    to_unit: str = Field(min_length=1, max_length=32)
    precision: int = Field(default=6, ge=0, le=12)


class UnitsConvertOutput(BaseModel):
    value: Decimal
    from_unit: str
    to_unit: str
    dimension: str
    factor: Decimal
