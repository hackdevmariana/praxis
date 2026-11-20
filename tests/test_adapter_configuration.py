import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.context import ToolContext
from app.providers.adapters import configure_adapters
from app.providers.alerts import SmtpAlertNotifier, get_alert_notifier
from app.providers.document_adapters import (
    LocalFileDocumentRepository,
    LocalFileDocumentStore,
    TesseractInvoiceOcr,
    WeasyPrintInvoiceRenderer,
)
from app.providers.documents import (
    get_artifact_store,
    get_document_repository,
    get_document_store,
    get_invoice_ocr,
    get_invoice_renderer,
)
from app.providers.google_calendar import get_calendar_connector
from app.providers.google_calendar_adapters import GoogleCalendarConnector
from app.providers.renewals import get_renewal_repository
from app.providers.savings import get_savings_repository

CTX = ToolContext(request_id="test")


def test_configure_adapters_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = {
        "PRAXIS_CALENDAR_ADAPTER": "google",
        "PRAXIS_GOOGLE_ACCESS_TOKEN": "token",
        "PRAXIS_DOCUMENTS_ADAPTER": "local",
        "PRAXIS_DOCUMENTS_DIR": str(tmp_path),
        "PRAXIS_PDF_RENDERER": "weasyprint",
        "PRAXIS_OCR_ADAPTER": "tesseract",
        "PRAXIS_ALERT_NOTIFIER": "smtp",
        "SMTP_HOST": "smtp.example.com",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    configure_adapters(reset=True)

    assert isinstance(get_calendar_connector(CTX), GoogleCalendarConnector)
    assert isinstance(get_document_store(CTX), LocalFileDocumentStore)
    assert isinstance(get_artifact_store(CTX), LocalFileDocumentStore)
    assert isinstance(get_document_repository(CTX), LocalFileDocumentRepository)
    assert isinstance(get_invoice_renderer(CTX), WeasyPrintInvoiceRenderer)
    assert isinstance(get_invoice_ocr(CTX), TesseractInvoiceOcr)
    assert isinstance(get_alert_notifier(CTX), SmtpAlertNotifier)


def test_configure_sql_repositories_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db.repositories import SqlRenewalRepository, SqlSavingsRepository

    monkeypatch.setenv("PRAXIS_SAVINGS_REPOSITORY", "sql")
    monkeypatch.setenv("PRAXIS_RENEWAL_REPOSITORY", "sql")
    engine = create_async_engine("postgresql+asyncpg://praxis:praxis@localhost/praxis")
    try:
        configure_adapters(engine, reset=True)

        assert isinstance(get_savings_repository(CTX), SqlSavingsRepository)
        assert isinstance(get_renewal_repository(CTX), SqlRenewalRepository)
    finally:
        asyncio.run(engine.dispose())
