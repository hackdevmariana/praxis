import asyncio
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.context import ToolContext
from app.money import quantize_money
from app.tools.datetime.business_days.schemas import BusinessDaysInput
from app.tools.datetime.business_days.tool import business_days
from app.tools.energy.carbon_footprint.schemas import CarbonInput
from app.tools.energy.carbon_footprint.tool import calculate_carbon_footprint
from app.tools.energy.self_consumption_payback.schemas import SelfConsumptionInput
from app.tools.energy.self_consumption_payback.tool import calculate_self_consumption_payback
from app.tools.energy.tariff_simulator.schemas import TariffSimulatorInput
from app.tools.energy.tariff_simulator.tool import simulate_tariffs
from app.tools.finance.break_even.schemas import BreakEvenInput
from app.tools.finance.break_even.tool import calculate_break_even
from app.tools.finance.business_kpi.schemas import BusinessKpiInput
from app.tools.finance.business_kpi.tool import calculate_business_kpi
from app.tools.finance.cashflow_13w.schemas import Cashflow13wInput
from app.tools.finance.cashflow_13w.tool import cashflow_13w
from app.tools.finance.discounts.schemas import DiscountsInput
from app.tools.finance.discounts.tool import calculate_discounts
from app.tools.finance.ebitda.schemas import EbitdaInput
from app.tools.finance.ebitda.tool import calculate_ebitda
from app.tools.finance.loan_schedule.schemas import LoanInput
from app.tools.finance.loan_schedule.tool import loan_schedule
from app.tools.finance.vat.schemas import VatInput
from app.tools.finance.vat.tool import calculate_vat
from app.tools.procurement.detect_price_increase.schemas import PriceIncreaseInput
from app.tools.procurement.detect_price_increase.tool import detect_price_increase
from app.tools.units.convert.schemas import UnitsConvertInput
from app.tools.units.convert.tool import convert

CTX = ToolContext(request_id="property")


@settings(max_examples=40, deadline=None)
@given(
    amount=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
    rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("100"), places=2),
)
def test_vat_add_keeps_base_and_total_consistent(amount: Decimal, rate: Decimal) -> None:
    output = asyncio.run(
        calculate_vat(VatInput.model_validate({"amount": amount, "rate": rate}), CTX)
    ).data

    assert output.base_amount == amount.quantize(Decimal("0.01"))
    assert output.vat_amount >= 0
    assert output.total_amount == output.base_amount + output.vat_amount


@settings(max_examples=40, deadline=None)
@given(
    amount=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
    discounts=st.lists(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("100"), places=2),
        min_size=1,
        max_size=4,
    ),
)
def test_discounts_are_bounded(amount: Decimal, discounts: list[Decimal]) -> None:
    output = asyncio.run(
        calculate_discounts(
            DiscountsInput.model_validate({"amount": amount, "discounts": discounts}),
            CTX,
        )
    ).data

    assert output.final_amount <= output.original_amount
    assert output.discount_amount >= 0
    assert output.final_amount == output.original_amount - output.discount_amount
    assert Decimal("0") <= output.effective_discount_pct <= Decimal("100")


@settings(max_examples=25, deadline=None)
@given(
    principal=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000000"), places=2),
    rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("30"), places=2),
    term=st.integers(min_value=1, max_value=120),
    loan_type=st.sampled_from(["french", "italian"]),
)
def test_loan_schedule_closes_at_zero(
    principal: Decimal, rate: Decimal, term: int, loan_type: str
) -> None:
    output = asyncio.run(
        loan_schedule(
            LoanInput.model_validate(
                {
                    "principal": principal,
                    "annual_rate": rate,
                    "term_months": term,
                    "type": loan_type,
                }
            ),
            CTX,
        )
    ).data

    assert len(output.schedule) == term
    assert output.schedule[-1].balance == Decimal("0.00")
    assert sum((item.principal for item in output.schedule), Decimal("0.00")) == output.principal
    assert output.total_paid == output.principal + output.total_interest


@settings(max_examples=30, deadline=None)
@given(start=st.dates(date(2026, 1, 1), date(2026, 12, 1)))
def test_business_days_are_bounded_by_calendar_days(start: date) -> None:
    end = start + timedelta(days=60)
    output = asyncio.run(
        business_days(
            BusinessDaysInput.model_validate({"start": start, "end": end}),
            CTX,
        )
    ).data

    assert output.calendar_days == 60
    assert 0 <= output.business_days <= output.calendar_days


@settings(max_examples=30, deadline=None)
@given(
    value=st.decimals(min_value=Decimal("-10000"), max_value=Decimal("10000"), places=2),
    precision=st.integers(min_value=0, max_value=8),
)
def test_units_identity_conversion(value: Decimal, precision: int) -> None:
    output = asyncio.run(
        convert(
            UnitsConvertInput.model_validate(
                {"value": value, "from_unit": "km", "to_unit": "km", "precision": precision}
            ),
            CTX,
        )
    ).data

    quantum = Decimal(1).scaleb(-precision)
    assert output.factor == Decimal("1")
    assert output.value == value.quantize(quantum, rounding=ROUND_HALF_UP)


@settings(max_examples=30, deadline=None)
@given(
    revenue=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000"), places=2),
    cogs=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
    opex=st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), places=2),
    depreciation=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
)
def test_business_kpi_identities(
    revenue: Decimal, cogs: Decimal, opex: Decimal, depreciation: Decimal
) -> None:
    output = asyncio.run(
        calculate_business_kpi(
            BusinessKpiInput.model_validate(
                {
                    "revenue": revenue,
                    "cogs": cogs,
                    "operating_expenses": opex,
                    "depreciation_amortization": depreciation,
                }
            ),
            CTX,
        )
    ).data

    assert output.ebit == output.gross_profit - opex
    assert output.ebitda == output.ebit + depreciation
    assert output.working_capital == Decimal("0.00")


@settings(max_examples=30, deadline=None)
@given(
    revenue=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
    cogs=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
    opex=st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), places=2),
    depreciation=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
)
def test_ebitda_identity(
    revenue: Decimal, cogs: Decimal, opex: Decimal, depreciation: Decimal
) -> None:
    output = asyncio.run(
        calculate_ebitda(
            EbitdaInput.model_validate(
                {
                    "revenue": revenue,
                    "cogs": cogs,
                    "operating_expenses": opex,
                    "depreciation_amortization": depreciation,
                }
            ),
            CTX,
        )
    ).data

    assert output.ebit == output.ebitda - depreciation


@settings(max_examples=30, deadline=None)
@given(
    fixed_costs=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2),
    variable_cost=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=2),
    margin=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000"), places=2),
    target_profit=st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), places=2),
)
def test_break_even_units_cover_costs(
    fixed_costs: Decimal, variable_cost: Decimal, margin: Decimal, target_profit: Decimal
) -> None:
    price = variable_cost + margin
    output = asyncio.run(
        calculate_break_even(
            BreakEvenInput.model_validate(
                {
                    "fixed_costs": fixed_costs,
                    "variable_cost_per_unit": variable_cost,
                    "price_per_unit": price,
                    "target_profit": target_profit,
                }
            ),
            CTX,
        )
    ).data

    assert Decimal(output.break_even_units) * price >= fixed_costs
    assert output.units_for_target_profit >= output.break_even_units


@settings(max_examples=25, deadline=None)
@given(
    opening=st.decimals(min_value=Decimal("-10000"), max_value=Decimal("10000"), places=2),
    inflows=st.lists(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
        min_size=13,
        max_size=13,
    ),
    outflows=st.lists(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
        min_size=13,
        max_size=13,
    ),
)
def test_cashflow_closing_balance_chain(
    opening: Decimal, inflows: list[Decimal], outflows: list[Decimal]
) -> None:
    output = asyncio.run(
        cashflow_13w(
            Cashflow13wInput.model_validate(
                {
                    "opening_balance": opening,
                    "weekly_inflows": inflows,
                    "weekly_outflows": outflows,
                }
            ),
            CTX,
        )
    ).data
    expected_end = opening + sum(
        (inflow - outflow for inflow, outflow in zip(inflows, outflows, strict=True)),
        Decimal("0.00"),
    )

    assert output.end_balance == expected_end
    assert output.min_balance <= output.end_balance
    assert output.weeks_with_negative_balance == sum(
        week.closing_balance < 0 for week in output.weeks
    )


@settings(max_examples=40, deadline=None)
@given(
    electricity=st.decimals(min_value=0, max_value=10000, places=2),
    gas=st.decimals(min_value=0, max_value=10000, places=2),
)
def test_carbon_scopes_are_additive(electricity: Decimal, gas: Decimal) -> None:
    output = asyncio.run(
        calculate_carbon_footprint(
            CarbonInput.model_validate({"electricity_kwh": electricity, "gas_kwh": gas}),
            CTX,
        )
    ).data

    assert output.total_kgco2e == (
        output.scope1_kgco2e + output.scope2_kgco2e + output.scope3_kgco2e
    )
    assert sum(item.emissions_kgco2e for item in output.by_source) == output.total_kgco2e


@settings(max_examples=40, deadline=None)
@given(
    consumption=st.decimals(min_value=0, max_value=10000, places=2),
    peak_share=st.decimals(min_value=0, max_value=100, places=2),
)
def test_tariff_ranking_is_consistent(consumption: Decimal, peak_share: Decimal) -> None:
    output = asyncio.run(
        simulate_tariffs(
            TariffSimulatorInput.model_validate(
                {
                    "annual_consumption_kwh": consumption,
                    "peak_share_pct": peak_share,
                    "contracted_power_kw": "4.6",
                    "tariffs": [
                        {
                            "name": "A",
                            "power_price_eur_kw_year": "40",
                            "energy_price_peak_eur_kwh": "0.22",
                            "energy_price_valley_eur_kwh": "0.14",
                            "standing_charge_eur_month": "2",
                        },
                        {
                            "name": "B",
                            "power_price_eur_kw_year": "35",
                            "energy_price_peak_eur_kwh": "0.19",
                            "energy_price_valley_eur_kwh": "0.12",
                            "standing_charge_eur_month": "3",
                        },
                    ],
                }
            ),
            CTX,
        )
    ).data
    costs = [item.annual_cost for item in output.ranking]

    assert costs == sorted(costs)
    assert [item.rank for item in output.ranking] == list(range(1, len(costs) + 1))
    assert [item.is_cheapest for item in output.ranking] == [
        item.rank == 1 for item in output.ranking
    ]
    assert all(
        item.savings_vs_most_expensive == max(costs) - item.annual_cost for item in output.ranking
    )


@settings(max_examples=20, deadline=None)
@given(price=st.decimals(min_value=Decimal("0.10"), max_value=Decimal("0.50"), places=2))
def test_payback_is_not_earlier_than_simple_payback(price: Decimal) -> None:
    output = asyncio.run(
        calculate_self_consumption_payback(
            SelfConsumptionInput.model_validate(
                {
                    "installation_kwp": "5",
                    "annual_production_kwh": "7000",
                    "self_consumption_pct": "60",
                    "capex": "5000",
                    "electricity_price_eur_kwh": price,
                    "export_price_eur_kwh": "0.06",
                    "annual_opex": "50",
                    "degradation_pct": "0.5",
                    "years": 25,
                }
            ),
            CTX,
        )
    ).data

    assert output.simple_payback_years is not None
    assert output.payback_years is not None
    assert output.payback_years >= output.simple_payback_years - Decimal("0.01")


@settings(max_examples=40, deadline=None)
@given(
    previous=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=2),
    current=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=2),
)
def test_detect_price_increase_change_is_consistent(previous: Decimal, current: Decimal) -> None:
    output = asyncio.run(
        detect_price_increase(
            PriceIncreaseInput.model_validate(
                {
                    "items": [
                        {
                            "supplier": "Proveedor",
                            "description": "Producto",
                            "previous_unit_price": previous,
                            "current_unit_price": current,
                        }
                    ]
                }
            ),
            CTX,
        )
    ).data
    alert = output.alerts[0]

    assert alert.change_amount == quantize_money(current - previous)
    assert alert.is_new_price is (previous == 0)
    assert (alert.change_pct is None) is alert.is_new_price
    assert output.anomalous_count == sum(item.is_anomalous for item in output.alerts)
