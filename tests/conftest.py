import pytest

from app.idempotency import idempotency_store
from app.providers.cache import clear_all_caches
from app.providers.google_calendar import set_calendar_connector


@pytest.fixture(autouse=True)
def clear_runtime_state() -> None:
    clear_all_caches()
    idempotency_store.clear()
    set_calendar_connector(None)
