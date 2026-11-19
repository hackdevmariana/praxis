from pathlib import Path

import pytest

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
    get_document_repository,
    get_document_store,
    get_invoice_ocr,
    get_invoice_renderer,
)
from app.providers.google_calendar import get_calendar_connector
from app.providers.google_calendar_adapters import GoogleCalendarConnector

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
    assert isinstance(get_document_repository(CTX), LocalFileDocumentRepository)
    assert isinstance(get_invoice_renderer(CTX), WeasyPrintInvoiceRenderer)
    assert isinstance(get_invoice_ocr(CTX), TesseractInvoiceOcr)
    assert isinstance(get_alert_notifier(CTX), SmtpAlertNotifier)
