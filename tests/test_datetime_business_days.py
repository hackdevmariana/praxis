import asyncio
from datetime import date

import pytest
from pydantic import ValidationError

from app.context import ToolContext
from app.tools.datetime.business_days.schemas import (
    BusinessDaysInput,
    BusinessDaysOutput,
)
from app.tools.datetime.business_days.tool import business_days

CTX = ToolContext(request_id="test")


def run(**kwargs: object) -> BusinessDaysOutput:
    result = asyncio.run(business_days(BusinessDaysInput.model_validate(kwargs), CTX))
    return result.data


def test_january_golden() -> None:
    output = run(start="2026-01-01", end="2026-01-08")

    assert output.business_days == 3
    assert output.calendar_days == 7
    assert [holiday.model_dump() for holiday in output.holidays_applied] == [
        {"date": date(2026, 1, 1), "name": "Año Nuevo", "scope": "national"},
        {"date": date(2026, 1, 6), "name": "Epifanía del Señor", "scope": "national"},
    ]


def test_easter_and_plain_week() -> None:
    easter = run(start="2026-04-01", end="2026-04-08")
    plain = run(start="2026-11-02", end="2026-11-09")

    assert easter.business_days == 4
    assert [holiday.date for holiday in easter.holidays_applied] == [date(2026, 4, 3)]
    assert plain.business_days == 5
    assert plain.holidays_applied == []


def test_include_end_and_same_day() -> None:
    inclusive = run(start="2026-11-02", end="2026-11-06", include_end=True)
    same_day = run(start="2026-11-13", end="2026-11-13")

    assert (inclusive.business_days, inclusive.calendar_days) == (5, 5)
    assert (same_day.business_days, same_day.calendar_days) == (0, 0)


def test_weekend_range() -> None:
    output = run(start="2026-11-14", end="2026-11-16")

    assert output.business_days == 0


def test_warnings_and_metadata_for_local_holidays() -> None:
    result = asyncio.run(
        business_days(
            BusinessDaysInput(
                start=date(2026, 11, 2),
                end=date(2026, 11, 9),
                municipality_code="28079",
            ),
            CTX,
        )
    )

    assert result.data.business_days == 5
    assert result.warnings == ["local_holidays_unavailable"]
    assert result.metadata_extra["holiday_dataset_version"] == "2026.1"
    assert result.metadata_extra["source"] == "seeder:holidays"
    assert (
        result.metadata_extra["source_detail"]
        == "python-holidays 0.108 (calendario festivo español)"
    )


def test_inverted_range_is_schema_error() -> None:
    with pytest.raises(ValidationError, match="posterior"):
        BusinessDaysInput.model_validate({"start": "2026-11-13", "end": "2026-11-01"})
