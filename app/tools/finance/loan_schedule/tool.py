from decimal import Decimal, localcontext

from app.context import ToolContext
from app.money import quantize_money
from app.registry import tool
from app.result import ToolResult, tool_result
from app.tools.finance.loan_schedule.schemas import (
    Installment,
    LoanInput,
    LoanOutput,
    LoanType,
)


@tool(
    name="finance.loan_schedule",
    version="1.0.0",
    title="Generar cuadro de amortización",
    permissions=["finance.calculate"],
    data_classification="business",
    read_only=True,
    idempotent=True,
    requires_confirmation=False,
    mcp_description=(
        "Genera el cuadro de amortización mensual de un préstamo por sistema francés "
        "(cuota constante) o italiano (capital constante). El tipo es nominal anual. "
        "No usar para leasing, hipotecas con carencia ni tipos variables."
    ),
)
async def loan_schedule(params: LoanInput, ctx: ToolContext) -> ToolResult[LoanOutput]:
    with localcontext() as context:
        context.prec = 60

        principal = quantize_money(params.principal)
        rate = params.annual_rate / 100 / 12
        term = params.term_months
        schedule: list[Installment] = []
        monthly_payment: Decimal | None = None

        if params.type is LoanType.french:
            if rate == 0:
                monthly_payment = quantize_money(principal / term)
            else:
                growth = (1 + rate) ** term
                monthly_payment = quantize_money(principal * rate / (1 - 1 / growth))

            balance = principal
            for period in range(1, term + 1):
                interest = quantize_money(balance * rate)
                if period == term:
                    principal_component = balance
                    payment = quantize_money(principal_component + interest)
                    balance = Decimal("0.00")
                else:
                    assert monthly_payment is not None
                    principal_component = quantize_money(monthly_payment - interest)
                    payment = quantize_money(principal_component + interest)
                    balance = quantize_money(balance - principal_component)
                schedule.append(
                    Installment(
                        period=period,
                        payment=payment,
                        interest=interest,
                        principal=principal_component,
                        balance=balance,
                    )
                )
        else:
            amortization = quantize_money(principal / term)
            balance = principal
            for period in range(1, term + 1):
                interest = quantize_money(balance * rate)
                principal_component = balance if period == term else amortization
                payment = quantize_money(principal_component + interest)
                balance = quantize_money(balance - principal_component)
                schedule.append(
                    Installment(
                        period=period,
                        payment=payment,
                        interest=interest,
                        principal=principal_component,
                        balance=balance,
                    )
                )

    total_interest = quantize_money(sum((item.interest for item in schedule), Decimal("0.00")))
    total_paid = quantize_money(sum((item.payment for item in schedule), Decimal("0.00")))

    return tool_result(
        LoanOutput(
            principal=principal,
            annual_rate=params.annual_rate,
            term_months=term,
            type=params.type,
            monthly_payment=monthly_payment,
            first_payment=schedule[0].payment,
            last_payment=schedule[-1].payment,
            total_interest=total_interest,
            total_paid=total_paid,
            schedule=schedule,
            currency=params.currency,
        )
    )
