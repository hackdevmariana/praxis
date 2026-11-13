"""Generate the versioned Spanish holidays dataset from python-holidays.

National holidays keep their fixed calendar date (even on weekends); autonomous
holidays are taken from each community's observed calendar and national dates
are removed to avoid duplicates.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import holidays

YEARS = tuple(range(2024, 2029))
VERSION = "2026.1"
VALID_UNTIL = date(2028, 12, 31)
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "holidays_es.json"

NATIONAL_NAME_OVERRIDES = {
    "Natividad del Señor": "Navidad",
    "Día de la Constitución Española": "Día de la Constitución",
}

COMMUNITY_NAMES = {
    "AN": "Andalucía",
    "AR": "Aragón",
    "AS": "Principado de Asturias",
    "CB": "Cantabria",
    "CE": "Ceuta",
    "CL": "Castilla y León",
    "CM": "Castilla-La Mancha",
    "CN": "Canarias",
    "CT": "Cataluña",
    "EX": "Extremadura",
    "GA": "Galicia",
    "IB": "Islas Baleares",
    "MC": "Región de Murcia",
    "MD": "Comunidad de Madrid",
    "ML": "Melilla",
    "NC": "Comunidad Foral de Navarra",
    "PV": "País Vasco",
    "RI": "La Rioja",
    "VC": "Comunidad Valenciana",
}

EXTRA_ALIASES = {
    "AS": ["Asturias"],
    "CT": ["Catalunya"],
    "IB": ["Illes Balears"],
    "MC": ["Murcia"],
    "MD": ["Madrid"],
    "NC": ["Navarra"],
    "PV": ["Euskadi"],
    "VC": ["Valenciana"],
}


def _holiday_names(year: int, subdiv: str | None = None, *, observed: bool) -> dict[date, str]:
    calendar = holidays.Spain(
        years=year,
        subdiv=subdiv,
        language="es",
        observed=observed,
    )
    return {day: str(name) for day, name in calendar.items()}


def _entries(names: dict[date, str]) -> list[dict[str, str]]:
    return [{"date": day.isoformat(), "name": names[day]} for day in sorted(names)]


def build_dataset() -> dict[str, Any]:
    national: dict[str, list[dict[str, str]]] = {}
    for year in YEARS:
        names = {
            day: NATIONAL_NAME_OVERRIDES.get(name, name)
            for day, name in _holiday_names(year, observed=False).items()
        }
        national[str(year)] = _entries(names)

    communities: dict[str, Any] = {}
    library_aliases = holidays.Spain.subdivisions_aliases
    for code, community_name in COMMUNITY_NAMES.items():
        aliases = {code, community_name, *EXTRA_ALIASES.get(code, [])}
        aliases.update(alias for alias, target in library_aliases.items() if target == code)

        yearly: dict[str, list[dict[str, str]]] = {}
        for year in YEARS:
            fixed_national = _holiday_names(year, observed=False)
            regional = _holiday_names(year, subdiv=code, observed=True)
            yearly[str(year)] = _entries(
                {day: name for day, name in regional.items() if day not in fixed_national}
            )

        communities[code] = {
            "name": community_name,
            "aliases": sorted(aliases),
            "holidays": yearly,
        }

    return {
        "version": VERSION,
        "source": f"python-holidays {holidays.__version__}",
        "generated_at": date.today().isoformat(),
        "valid_until": VALID_UNTIL.isoformat(),
        "years": list(YEARS),
        "national": national,
        "communities": communities,
    }


def main() -> None:
    dataset = build_dataset()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    national_count = sum(len(items) for items in dataset["national"].values())
    community_count = sum(
        len(items)
        for community in dataset["communities"].values()
        for items in community["holidays"].values()
    )
    print(
        f"Wrote {OUTPUT} - {national_count} national and "
        f"{community_count} autonomous holiday entries"
    )


if __name__ == "__main__":
    main()
