from datetime import date

import pytest

from app.holidays import load_dataset, lookup_holidays, resolve_community


def test_dataset_metadata_and_coverage() -> None:
    dataset = load_dataset()

    assert dataset.version == "2026.1"
    assert dataset.source.startswith("python-holidays ")
    assert dataset.valid_until == date(2028, 12, 31)
    assert dataset.years == [2024, 2025, 2026, 2027, 2028]


def test_national_holidays_2026_are_canonical() -> None:
    lookup = lookup_holidays(2026)

    assert lookup.warnings == ()
    assert len(lookup.holidays) == 10
    assert lookup.holidays[0].date == date(2026, 1, 1)
    assert lookup.holidays[0].name == "Año Nuevo"
    assert all(holiday.scope == "national" for holiday in lookup.holidays)
    assert (date(2026, 12, 6), "Día de la Constitución") in {
        (holiday.date, holiday.name) for holiday in lookup.holidays
    }
    assert (date(2026, 12, 25), "Navidad") in {
        (holiday.date, holiday.name) for holiday in lookup.holidays
    }


def test_community_holidays_are_added_without_duplicates() -> None:
    lookup = lookup_holidays(2026, community="Madrid")

    assert lookup.warnings == ()
    assert len(lookup.holidays) == 14
    autonomous = {
        (holiday.date, holiday.name) for holiday in lookup.holidays if holiday.scope == "autonomous"
    }
    assert autonomous == {
        (date(2026, 4, 2), "Jueves Santo"),
        (date(2026, 5, 2), "Fiesta de la Comunidad de Madrid"),
        (date(2026, 11, 2), "Lunes siguiente a Todos los Santos"),
        (date(2026, 12, 7), "Lunes siguiente a Día de la Constitución Española"),
    }
    assert lookup.holidays == tuple(sorted(lookup.holidays, key=lambda h: (h.date, h.name)))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MD", "MD"),
        ("Madrid", "MD"),
        ("Comunidad de Madrid", "MD"),
        ("madrid", "MD"),
        ("Catalunya", "CT"),
        ("Andalucia", "AN"),
        ("Valenciana", "VC"),
    ],
)
def test_resolve_community_accepts_codes_and_aliases(value: str, expected: str) -> None:
    assert resolve_community(value) == expected


def test_unknown_community_adds_warning() -> None:
    lookup = lookup_holidays(2026, community="Atlántida")

    assert lookup.warnings == ("community_not_found",)
    assert len(lookup.holidays) == 10


def test_municipality_holidays_are_not_invented() -> None:
    lookup = lookup_holidays(2026, municipality_code="28079")

    assert lookup.warnings == ("local_holidays_unavailable",)
    assert all(holiday.scope != "local" for holiday in lookup.holidays)


def test_year_outside_dataset_is_reported() -> None:
    lookup = lookup_holidays(2030)

    assert lookup.warnings == ("holiday_dataset_incomplete",)
    assert lookup.holidays == ()


def test_dataset_has_no_duplicate_dates() -> None:
    lookup = lookup_holidays(2027, community="CT")
    dates = [holiday.date for holiday in lookup.holidays]

    assert len(dates) == len(set(dates))
