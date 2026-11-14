import asyncio
from datetime import date

import pytest
import time_machine
from pydantic import ValidationError

from app.context import ToolContext
from app.errors import ToolError
from app.tools.datetime.calc.schemas import DateCalcInput, DateCalcOutput, Operation
from app.tools.datetime.calc.tool import date_calc

CTX = ToolContext(request_id="test")


def run(**kwargs: object) -> DateCalcOutput:
    result = asyncio.run(date_calc(DateCalcInput.model_validate(kwargs), CTX))
    return result.data


def test_today_uses_madrid_clock() -> None:
    with time_machine.travel("2026-11-13T10:00:00Z", tick=False):
        output = run(operation=Operation.today, timezone="Europe/Madrid")

    assert output.operation is Operation.today
    assert output.date == date(2026, 11, 13)


def test_add_and_subtract_days() -> None:
    added = run(operation=Operation.add_days, date="2026-11-13", days=10)
    subtracted = run(operation=Operation.add_days, date="2026-11-13", days=-10)
    crossed = run(operation=Operation.add_days, date="2026-12-31", days=1)
    leap = run(operation=Operation.add_days, date="2028-02-28", days=1)

    assert added.date == date(2026, 11, 23)
    assert subtracted.date == date(2026, 11, 3)
    assert crossed.date == date(2027, 1, 1)
    assert leap.date == date(2028, 2, 29)


def test_diff_days_is_signed() -> None:
    forward = run(operation=Operation.diff_days, date="2026-11-01", date_b="2026-11-13")
    backward = run(operation=Operation.diff_days, date="2026-11-13", date_b="2026-11-01")

    assert forward.days_diff == 12
    assert backward.days_diff == -12


def test_weekday_uses_iso_number_and_spanish_name() -> None:
    output = run(operation=Operation.weekday, date="2026-11-13")

    assert output.weekday == 5
    assert output.weekday_name == "viernes"


def test_week_info_golden() -> None:
    output = run(operation=Operation.week_info, date="2026-11-13")

    assert output.iso_week == 46
    assert output.iso_year == 2026
    assert output.quarter == 4
    assert output.semester == 2
    assert output.day_of_year == 317


def test_missing_required_date_is_schema_error() -> None:
    with pytest.raises(ValidationError, match="date"):
        DateCalcInput(operation=Operation.add_days, days=1)


def test_invalid_timezone_is_tool_error() -> None:
    with pytest.raises(ToolError) as error:
        run(operation=Operation.today, timezone="Europe/Atlantis")

    assert error.value.code == "invalid_params"
