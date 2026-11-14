from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BusinessDaysInput(BaseModel):
    start: date
    end: date
    community: str | None = None
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    include_end: bool = False

    @model_validator(mode="after")
    def valid_range(self) -> "BusinessDaysInput":
        if self.start > self.end:
            raise ValueError("start no puede ser posterior a end")
        return self


class HolidayApplied(BaseModel):
    date: date
    name: str
    scope: Literal["national", "autonomous", "local"]


class BusinessDaysOutput(BaseModel):
    business_days: int
    calendar_days: int
    holidays_applied: list[HolidayApplied]
