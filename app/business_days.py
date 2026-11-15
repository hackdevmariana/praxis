"""Business day counting shared by date and calendar tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from app.clock import MADRID
from app.errors import ErrorCode, ToolError
from app.holidays import AppliedHoliday, load_dataset, lookup_holidays


@dataclass(frozen=True, slots=True)
class BusinessDayResult:
    business_days: int
    calendar_days: int
    holidays: tuple[AppliedHoliday, ...]
    warnings: tuple[str, ...]
    dataset_version: str
    valid_until: date


def count_business_days(
    start: date,
    end: date,
    *,
    include_end: bool = False,
    community: str | None = None,
    municipality_code: str | None = None,
) -> BusinessDayResult:
    """Count weekdays in [start, end) or [start, end], excluding holidays."""
    if start > end:
        raise ToolError(ErrorCode.INVALID_PARAMS, "start no puede ser posterior a end")

    dataset = load_dataset()
    last = end if include_end else end - timedelta(days=1)
    if last < start:
        return BusinessDayResult(
            business_days=0,
            calendar_days=0,
            holidays=(),
            warnings=(),
            dataset_version=dataset.version,
            valid_until=dataset.valid_until,
        )

    warnings: list[str] = []
    holidays_by_date: dict[date, AppliedHoliday] = {}
    for year in range(start.year, last.year + 1):
        lookup = lookup_holidays(
            year,
            community=community,
            municipality_code=municipality_code,
        )
        for warning in lookup.warnings:
            if warning not in warnings:
                warnings.append(warning)
        for holiday in lookup.holidays:
            if start <= holiday.date <= last:
                holidays_by_date.setdefault(holiday.date, holiday)

    holidays = tuple(sorted(holidays_by_date.values(), key=lambda h: (h.date, h.name)))
    business_days = 0
    current = start
    while current <= last:
        if current.weekday() < 5 and current not in holidays_by_date:
            business_days += 1
        current += timedelta(days=1)

    return BusinessDayResult(
        business_days=business_days,
        calendar_days=(last - start).days + 1,
        holidays=holidays,
        warnings=tuple(warnings),
        dataset_version=dataset.version,
        valid_until=dataset.valid_until,
    )


def holiday_source_detail() -> str:
    """Describe the real provenance of the holidays dataset."""
    return f"{load_dataset().source} (calendario festivo español)"


def holiday_metadata(result: BusinessDayResult) -> dict[str, Any]:
    """Metadata fields tied to the versioned holidays dataset."""
    return {
        "valid_until": datetime.combine(result.valid_until, time.min, tzinfo=MADRID),
        "holiday_dataset_version": result.dataset_version,
        "source_detail": holiday_source_detail(),
    }
