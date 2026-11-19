from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class Channel(StrEnum):
    none = "none"
    email = "email"
    whatsapp = "whatsapp"


class ContractRenewalInput(BaseModel):
    contract_id: UUID
    renewal_date: date
    notice_days: list[int] = Field(
        default_factory=lambda: [60, 30, 15], min_length=1, max_length=10
    )
    channel: Channel = Channel.none
    recipient: EmailStr | None = None
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("notice_days")
    @classmethod
    def validate_notice_days(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("notice_days no puede contener duplicados")
        if any(day < 1 or day > 365 for day in value):
            raise ValueError("notice_days debe estar entre 1 y 365")
        return value


class ScheduleEntry(BaseModel):
    days_before: int
    trigger_at: datetime
    channel: Channel
    status: str


class ContractRenewalOutput(BaseModel):
    alert_rule_id: str
    renewal_date: date
    next_trigger_at: datetime | None
    schedule: list[ScheduleEntry]
    deduplicated: bool
