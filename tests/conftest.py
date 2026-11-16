import pytest

from app.providers.cache import clear_all_caches


@pytest.fixture(autouse=True)
def clear_provider_caches() -> None:
    clear_all_caches()
