from __future__ import annotations

from datetime import date as DateType
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Operation(StrEnum):
    today = "today"
    add_days = "add_days"
    diff_days = "diff_days"
    weekday = "weekday"
    week_info = "week_info"


class DateCalcInput(BaseModel):
    operation: Operation
    date: DateType | None = None
    date_b: DateType | None = None
    days: int | None = Field(default=None, ge=-36500, le=36500)
    timezone: str = "Europe/Madrid"

    @model_validator(mode="after")
    def requirements(self) -> DateCalcInput:
        required = {
            Operation.add_days: ("date", "days"),
            Operation.diff_days: ("date", "date_b"),
            Operation.weekday: ("date",),
            Operation.week_info: ("date",),
        }.get(self.operation, ())
        for field in required:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' es obligatorio para {self.operation.value}")
        return self


class DateCalcOutput(BaseModel):
    operation: Operation
    date: DateType | None = None
    days_diff: int | None = None
    weekday: int | None = None
    weekday_name: str | None = None
    iso_week: int | None = None
    iso_year: int | None = None
    quarter: int | None = None
    semester: int | None = None
    day_of_year: int | None = None
