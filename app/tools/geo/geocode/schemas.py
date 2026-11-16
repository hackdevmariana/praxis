from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GeocodeInput(BaseModel):
    address: str | None = Field(default=None, min_length=3, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    limit: int = Field(default=1, ge=1, le=5)

    @model_validator(mode="after")
    def only_one_mode(self) -> "GeocodeInput":
        forward = self.address is not None
        reverse = self.latitude is not None and self.longitude is not None
        if forward == reverse:
            raise ValueError("Indica 'address' o 'latitude'+'longitude', no ambos")
        return self


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    normalized_address: str
    ine_code: str | None = None
    municipality: str | None = None
    province: str | None = None
    postal_code: str | None = None
    confidence: float
    source: str


class GeocodeOutput(BaseModel):
    mode: Literal["forward", "reverse"]
    results: list[GeocodeResult]
