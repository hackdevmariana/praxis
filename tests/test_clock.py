from datetime import UTC, date, datetime

import time_machine
from app.clock import MADRID, now, today


@time_machine.travel(datetime(2026, 11, 13, 10, 0, tzinfo=UTC))
def test_now_uses_madrid_timezone() -> None:
    current = now()

    assert current.isoformat() == "2026-11-13T11:00:00+01:00"
    assert current.tzinfo is not None


@time_machine.travel(datetime(2026, 11, 13, 23, 30, tzinfo=UTC))
def test_today_uses_madrid_calendar_date() -> None:
    assert today() == date(2026, 11, 14)


def test_madrid_is_default_timezone() -> None:
    assert now().tzinfo is not None
    assert now().utcoffset() is not None
    assert MADRID.key == "Europe/Madrid"
