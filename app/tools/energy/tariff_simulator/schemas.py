from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class TariffInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    power_price_eur_kw_year: Decimal = Field(ge=0)
    energy_price_peak_eur_kwh: Decimal = Field(ge=0)
    energy_price_valley_eur_kwh: Decimal = Field(ge=0)
    standing_charge_eur_month: Decimal = Field(default=Decimal("0"), ge=0)


class TariffSimulatorInput(BaseModel):
    annual_consumption_kwh: Decimal = Field(ge=0)
    peak_share_pct: Decimal = Field(default=Decimal("40"), ge=0, le=100)
    contracted_power_kw: Decimal = Field(gt=0)
    tariffs: list[TariffInput] = Field(min_length=2, max_length=5)

    @field_validator("tariffs")
    @classmethod
    def nombres_unicos(cls, value: list[TariffInput]) -> list[TariffInput]:
        if len({tariff.name for tariff in value}) != len(value):
            raise ValueError("Los nombres de tarifa deben ser únicos")
        return value


class TariffResult(BaseModel):
    name: str
    peak_kwh: Decimal
    valley_kwh: Decimal
    power_cost: Decimal
    energy_cost: Decimal
    standing_cost: Decimal
    annual_cost: Decimal
    monthly_avg: Decimal
    rank: int
    savings_vs_most_expensive: Decimal
    is_cheapest: bool


class TariffSimulatorOutput(BaseModel):
    annual_consumption_kwh: Decimal
    peak_kwh: Decimal
    valley_kwh: Decimal
    currency: str
    ranking: list[TariffResult]
    savings_pct_best: Decimal | None
