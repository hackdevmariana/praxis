from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class CreateEventInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start: datetime
    end: datetime
    calendar_id: str = Field(default="primary", min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=8000)
    location: str | None = Field(default=None, max_length=500)
    attendees: list[EmailStr] = Field(default_factory=list, max_length=100)
    all_day: bool = False
    timezone: str = "Europe/Madrid"
    send_notifications: bool = False
    recurrence_rrule: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("recurrence_rrule")
    @classmethod
    def validate_rrule(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("RRULE:") or any(char.isspace() for char in value):
            raise ValueError("recurrence_rrule debe empezar por RRULE: y no contener espacios")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "CreateEventInput":
        if self.start >= self.end:
            raise ValueError("start debe ser anterior a end")
        return self


class CreateEventOutput(BaseModel):
    event_id: str
    html_link: str | None
    status: str
    start: str
    end: str
    created: datetime
    deduplicated: bool
