"""Spanish holidays dataset loader and lookup helpers."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

DATASET_PATH = Path(__file__).resolve().parent / "data" / "holidays_es.json"

HolidayScope = Literal["national", "autonomous", "local"]


class HolidayEntry(BaseModel):
    date: date
    name: str


class CommunityHolidays(BaseModel):
    name: str
    aliases: list[str]
    holidays: dict[int, list[HolidayEntry]]


class HolidaysDataset(BaseModel):
    version: str
    source: str
    generated_at: date
    valid_until: date
    years: list[int]
    national: dict[int, list[HolidayEntry]]
    communities: dict[str, CommunityHolidays]


@dataclass(frozen=True, slots=True)
class AppliedHoliday:
    date: date
    name: str
    scope: HolidayScope


@dataclass(frozen=True, slots=True)
class HolidayLookup:
    holidays: tuple[AppliedHoliday, ...]
    warnings: tuple[str, ...]


@lru_cache(maxsize=1)
def load_dataset() -> HolidaysDataset:
    return HolidaysDataset.model_validate_json(DATASET_PATH.read_text(encoding="utf-8"))


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.casefold().split())


@lru_cache(maxsize=64)
def resolve_community(value: str) -> str | None:
    """Resolve a community code or name (accent/case-insensitive) to its code."""
    target = _normalize(value)
    for code, community in load_dataset().communities.items():
        if target == _normalize(code):
            return code
        if any(target == _normalize(alias) for alias in community.aliases):
            return code
    return None


def lookup_holidays(
    year: int,
    *,
    community: str | None = None,
    municipality_code: str | None = None,
) -> HolidayLookup:
    """Return the holidays applicable to a year and optional location."""
    dataset = load_dataset()
    warnings: list[str] = []

    if year not in dataset.years:
        warnings.append("holiday_dataset_incomplete")

    entries = [
        AppliedHoliday(date=holiday.date, name=holiday.name, scope="national")
        for holiday in dataset.national.get(year, [])
    ]

    if community is not None:
        code = resolve_community(community)
        if code is None:
            warnings.append("community_not_found")
        else:
            entries.extend(
                AppliedHoliday(date=holiday.date, name=holiday.name, scope="autonomous")
                for holiday in dataset.communities[code].holidays.get(year, [])
            )

    if municipality_code is not None:
        warnings.append("local_holidays_unavailable")

    entries.sort(key=lambda holiday: (holiday.date, holiday.name))
    return HolidayLookup(holidays=tuple(entries), warnings=tuple(warnings))
