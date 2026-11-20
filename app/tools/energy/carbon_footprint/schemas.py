from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

FACTOR_KEYS = ("electricity", "natural_gas", "diesel", "gasoline", "waste", "transport")


class CarbonInput(BaseModel):
    electricity_kwh: Decimal = Field(default=Decimal("0"), ge=0)
    gas_kwh: Decimal = Field(default=Decimal("0"), ge=0)
    diesel_liters: Decimal = Field(default=Decimal("0"), ge=0)
    gasoline_liters: Decimal = Field(default=Decimal("0"), ge=0)
    waste_kg: Decimal = Field(default=Decimal("0"), ge=0)
    transport_km: Decimal = Field(default=Decimal("0"), ge=0)
    period_start: date | None = None
    period_end: date | None = None
    factor_overrides: dict[str, Decimal] | None = None

    @field_validator("factor_overrides")
    @classmethod
    def factores_validos(cls, value: dict[str, Decimal] | None) -> dict[str, Decimal] | None:
        if value is None:
            return None
        for key, factor in value.items():
            if key not in FACTOR_KEYS:
                raise ValueError(f"Factor desconocido: {key}")
            if factor < 0:
                raise ValueError("Los factores no pueden ser negativos")
        return value

    @model_validator(mode="after")
    def periodo(self) -> "CarbonInput":
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("Aporta period_start y period_end juntos")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("period_start no puede ser posterior a period_end")
        return self


class SourceEmission(BaseModel):
    activity: str
    scope: int
    quantity: Decimal
    unit: str
    factor: Decimal
    emissions_kgco2e: Decimal


class CarbonOutput(BaseModel):
    period_start: date | None
    period_end: date | None
    scope1_kgco2e: Decimal
    scope2_kgco2e: Decimal
    scope3_kgco2e: Decimal
    total_kgco2e: Decimal
    intensity_kgco2e_per_kwh: Decimal | None
    by_source: list[SourceEmission]
