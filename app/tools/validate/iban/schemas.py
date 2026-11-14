from pydantic import BaseModel, Field


class IbanInput(BaseModel):
    iban: str = Field(min_length=4, max_length=42)
    bic: str | None = Field(default=None, max_length=11)


class IbanOutput(BaseModel):
    valid: bool
    normalized: str
    country: str | None = None
    bban: str | None = None
    bic_valid: bool | None = None
    reason: str | None = None
    warning: str | None = "Un IBAN válido no implica que la cuenta exista o esté operativa."
