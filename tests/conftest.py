import pytest

from app.audit import NoopExecutionLogStore, set_execution_log_store
from app.idempotency import InMemoryIdempotencyStore, set_idempotency_store
from app.providers.cache import clear_all_caches
from app.providers.contracts import set_contract_repository
from app.providers.documents import set_document_adapters, set_document_repository
from app.providers.google_calendar import set_calendar_connector


@pytest.fixture(autouse=True)
def clear_runtime_state() -> None:
    clear_all_caches()
    set_idempotency_store(InMemoryIdempotencyStore())
    set_execution_log_store(NoopExecutionLogStore())
    set_calendar_connector(None)
    set_contract_repository(None)
    set_document_adapters()
    set_document_repository(None)
