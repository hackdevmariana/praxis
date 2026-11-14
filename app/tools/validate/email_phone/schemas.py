from pydantic import BaseModel, Field, model_validator


class EmailPhoneInput(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    default_region: str = Field(default="ES", min_length=2, max_length=2)

    @model_validator(mode="after")
    def at_least_one(self) -> "EmailPhoneInput":
        if not self.email and not self.phone:
            raise ValueError("Indica al menos email o phone")
        return self


class EmailPhoneOutput(BaseModel):
    email_valid: bool | None = None
    email_normalized: str | None = None
    email_reason: str | None = None
    phone_valid: bool | None = None
    phone_e164: str | None = None
    phone_international: str | None = None
    phone_type: str | None = None
    phone_country: str | None = None
    phone_reason: str | None = None
