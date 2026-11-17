import asyncio

from app.auth import AuthSettings
from app.db.engine import create_db_engine, database_url_from_env
from app.idempotency import InMemoryIdempotencyStore
from app.main import create_app

URL = "postgresql+asyncpg://praxis:praxis@localhost:5432/praxis"


def test_database_url_is_read_from_environment() -> None:
    assert database_url_from_env({}) is None
    assert database_url_from_env({"DATABASE_URL": URL}) == URL


def test_engine_factory_is_only_created_with_url() -> None:
    assert create_db_engine(None, env={}) is None

    engine = create_db_engine(URL, env={})
    assert engine is not None
    asyncio.run(engine.dispose())


def test_app_without_database_uses_in_memory_stores() -> None:
    app = create_app(AuthSettings(), database_url="")

    assert app.state.engine is None
    assert isinstance(app.state.idempotency_store, InMemoryIdempotencyStore)


def test_app_accepts_injected_idempotency_store() -> None:
    store = InMemoryIdempotencyStore()

    app = create_app(
        AuthSettings(),
        idempotency_store=store,
        database_url="",
    )

    assert app.state.idempotency_store is store
