import asyncio
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.context import ToolContext
from app.tools.datetime.business_days.schemas import BusinessDaysInput
from app.tools.datetime.business_days.tool import business_days
from app.tools.finance.discounts.schemas import DiscountsInput
from app.tools.finance.discounts.tool import calculate_discounts
from app.tools.finance.loan_schedule.schemas import LoanInput
from app.tools.finance.loan_schedule.tool import loan_schedule
from app.tools.finance.vat.schemas import VatInput
from app.tools.finance.vat.tool import calculate_vat
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
