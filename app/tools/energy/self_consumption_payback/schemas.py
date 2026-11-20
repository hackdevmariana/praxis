from decimal import Decimal

from pydantic import BaseModel, Field


class SelfConsumptionInput(BaseModel):
    installation_kwp: Decimal = Field(gt=0)
    annual_production_kwh: Decimal = Field(gt=0)
    self_consumption_pct: Decimal = Field(ge=0, le=100)
    capex: Decimal = Field(ge=0, decimal_places=2)
    electricity_price_eur_kwh: Decimal = Field(ge=0)
    export_price_eur_kwh: Decimal = Field(default=Decimal("0"), ge=0)
    annual_opex: Decimal = Field(default=Decimal("0"), ge=0)
    degradation_pct: Decimal = Field(default=Decimal("0.5"), ge=0, le=10)
    years: int = Field(default=25, ge=1, le=40)
    discount_rate_pct: Decimal = Field(default=Decimal("3"), ge=0, le=30)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class CashflowYear(BaseModel):
    year: int
    production_kwh: Decimal
    self_consumed_kwh: Decimal
    exported_kwh: Decimal
    savings: Decimal
    cumulative_savings: Decimal


class SelfConsumptionOutput(BaseModel):
    year1_savings: Decimal
    simple_payback_years: Decimal | None
    payback_years: Decimal | None
    npv: Decimal
    irr_pct: Decimal | None
    cashflows: list[CashflowYear]
    currency: str
