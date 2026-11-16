from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ListEventsInput(BaseModel):
    start: datetime
    end: datetime
    calendar_id: str = Field(default="primary", min_length=1, max_length=256)
    max_results: int = Field(default=50, ge=1, le=250)
    timezone: str = "Europe/Madrid"

    @model_validator(mode="after")
    def validate_range(self) -> "ListEventsInput":
        if self.start >= self.end:
            raise ValueError("start debe ser anterior a end")
        return self


class CalendarEventOut(BaseModel):
    id: str
    title: str
    start: str
    end: str
    location: str | None
    attendees: list[str]
    status: str
    is_all_day: bool
    html_link: str | None


class ListEventsOutput(BaseModel):
    events: list[CalendarEventOut]
    next_page_token: str | None
    timezone: str
