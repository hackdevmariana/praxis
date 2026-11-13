"""Clock helpers pinned to the project's default timezone."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


def now(tz: ZoneInfo = MADRID) -> datetime:
    """Return the current instant in the requested timezone."""
    return datetime.now(tz)


def today(tz: ZoneInfo = MADRID) -> date:
    """Return the current date in the requested timezone."""
    return now(tz).date()
