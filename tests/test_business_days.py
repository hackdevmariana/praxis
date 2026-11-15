from datetime import date

import pytest

from app.business_days import count_business_days, holiday_metadata
from app.errors import ToolError


def test_january_with_national_holidays() -> None:
    result = count_business_days(date(2026, 1, 1), date(2026, 1, 8))

    assert result.business_days == 3
    assert result.calendar_days == 7
    assert [(h.date, h.name, h.scope) for h in result.holidays] == [
        (date(2026, 1, 1), "Año Nuevo", "national"),
        (date(2026, 1, 6), "Epifanía del Señor", "national"),
    ]
    assert result.warnings == ()


def test_holy_week_and_plain_week() -> None:
    easter = count_business_days(date(2026, 4, 1), date(2026, 4, 8))
    plain = count_business_days(date(2026, 11, 2), date(2026, 11, 9))

    assert easter.business_days == 4
    assert plain.business_days == 5
    assert [h.date for h in easter.holidays] == [date(2026, 4, 3)]


def test_include_end_and_same_day() -> None:
    inclusive = count_business_days(date(2026, 11, 2), date(2026, 11, 6), include_end=True)
    exclusive = count_business_days(date(2026, 11, 13), date(2026, 11, 13))
    same_inclusive = count_business_days(date(2026, 11, 13), date(2026, 11, 13), include_end=True)

    assert (inclusive.business_days, inclusive.calendar_days) == (5, 5)
    assert (exclusive.business_days, exclusive.calendar_days) == (0, 0)
    assert (same_inclusive.business_days, same_inclusive.calendar_days) == (1, 1)


def test_full_weekend_has_no_business_days() -> None:
    result = count_business_days(date(2026, 11, 14), date(2026, 11, 16))

    assert result.business_days == 0
    assert result.calendar_days == 2


def test_community_holiday_is_excluded() -> None:
    result = count_business_days(date(2026, 11, 2), date(2026, 11, 9), community="MD")

    assert result.business_days == 4
    assert result.holidays[0].date == date(2026, 11, 2)
    assert result.holidays[0].scope == "autonomous"


def test_local_holidays_warning_is_propagated() -> None:
    result = count_business_days(date(2026, 11, 2), date(2026, 11, 9), municipality_code="28079")

    assert result.warnings == ("local_holidays_unavailable",)
    assert result.business_days == 5


def test_range_outside_dataset_warns() -> None:
    result = count_business_days(date(2030, 1, 1), date(2030, 1, 8))

    assert result.warnings == ("holiday_dataset_incomplete",)
    assert result.business_days == 5


def test_inverted_range_raises_tool_error() -> None:
    with pytest.raises(ToolError) as error:
        count_business_days(date(2026, 11, 13), date(2026, 11, 1))

    assert error.value.code == "invalid_params"


def test_holiday_metadata_uses_dataset_version() -> None:
    result = count_business_days(date(2026, 1, 1), date(2026, 1, 8))
    metadata = holiday_metadata(result)

    assert metadata["holiday_dataset_version"] == "2026.1"
    assert metadata["source_detail"] == "python-holidays 0.108 (calendario festivo español)"
    assert metadata["valid_until"].year == 2028
