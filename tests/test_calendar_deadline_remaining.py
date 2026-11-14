import asyncio
from datetime import date

import pytest
import time_machine
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ToolError
from app.tools.calendar.deadline_remaining.schemas import (
    DeadlineInput,
    DeadlineOutput,
    Period,
)
from app.tools.calendar.deadline_remaining.tool import deadline_remaining

CTX = ToolContext(request_id="test")


def run(**kwargs: object) -> DeadlineOutput:
    result = asyncio.run(deadline_remaining(DeadlineInput.model_validate(kwargs), CTX))
    return result.data


def test_month_golden() -> None:
    output = run(period=Period.month, reference_date="2026-11-13")

    assert output.period_start == date(2026, 11, 1)
    assert output.deadline == date(2026, 11, 30)
    assert output.days_remaining == 17
    assert output.business_days_remaining == 11
    assert output.holidays_applied == []


def test_quarter_golden() -> None:
    output = run(period=Period.quarter, reference_date="2026-11-13")

    assert output.period_start == date(2026, 10, 1)
    assert output.deadline == date(2026, 12, 31)
    assert output.days_remaining == 48
    assert output.business_days_remaining == 32
    assert [(holiday.date, holiday.name) for holiday in output.holidays_applied] == [
        (date(2026, 12, 6), "Día de la Constitución"),
        (date(2026, 12, 8), "Inmaculada Concepción"),
        (date(2026, 12, 25), "Navidad"),
    ]


def test_year_golden() -> None:
    output = run(period=Period.year, reference_date="2026-11-13")

    assert output.period_start == date(2026, 1, 1)
    assert output.deadline == date(2026, 12, 31)
    assert output.days_remaining == 48
    assert output.business_days_remaining == 32


def test_deadline_day_has_zero_remaining() -> None:
    output = run(period=Period.month, reference_date="2026-11-30")

    assert output.days_remaining == 0
    assert output.business_days_remaining == 0


def test_leap_february() -> None:
    output = run(period=Period.month, reference_date="2028-02-15")

    assert output.deadline == date(2028, 2, 29)
    assert output.days_remaining == 14
    assert output.business_days_remaining == 10


def test_today_uses_madrid_clock() -> None:
    with time_machine.travel("2026-11-13T10:00:00Z", tick=False):
        output = run(period=Period.month)

    assert output.period_start == date(2026, 11, 1)
    assert output.deadline == date(2026, 11, 30)


def test_invalid_period_and_timezone() -> None:
    with pytest.raises(ValidationError):
        DeadlineInput.model_validate({"period": "week"})

    with pytest.raises(ToolError) as error:
        run(period=Period.month, timezone="Europe/Atlantis")

    assert error.value.code == "invalid_params"
