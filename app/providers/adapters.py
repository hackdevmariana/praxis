from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from app.providers.alerts import SmtpAlertNotifier, set_alert_notifier, set_alert_rule_repository
from app.providers.contracts import set_contract_repository
from app.providers.document_adapters import (
    LocalFileDocumentRepository,
    LocalFileDocumentStore,
    TesseractInvoiceOcr,
    WeasyPrintInvoiceRenderer,
)
from app.providers.documents import set_document_adapters, set_document_repository
from app.providers.google_calendar import set_calendar_connector, set_event_repository
from app.providers.google_calendar_adapters import (
    GoogleCalendarConnector,
    RefreshTokenProvider,
    StaticTokenProvider,
)


def _flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, ""))
    except ValueError:
        return default


def configure_adapters(engine: AsyncEngine | None = None, *, reset: bool = False) -> None:
    """Instala los adaptadores reales indicados por variables de entorno."""
    if reset:
        set_calendar_connector(None)
        set_event_repository(None)
        set_contract_repository(None)
        set_alert_rule_repository(None)
        set_alert_notifier(None)
        set_document_adapters()
        set_document_repository(None)

    if os.getenv("PRAXIS_CALENDAR_ADAPTER", "").lower() == "google":
        static_token = os.getenv("PRAXIS_GOOGLE_ACCESS_TOKEN")
        if static_token:
            tokens = StaticTokenProvider(static_token)
        else:
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
            if client_id and client_secret and refresh_token:
                tokens = RefreshTokenProvider(
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=refresh_token,
                    token_url=os.getenv("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token"),
                )
            else:
                tokens = None
        if tokens is not None:
            set_calendar_connector(GoogleCalendarConnector(tokens))

    store = None
    renderer = None
    ocr = None
    repository = None
    if os.getenv("PRAXIS_DOCUMENTS_ADAPTER", "").lower() == "local":
        root = Path(os.getenv("PRAXIS_DOCUMENTS_DIR", "/var/lib/praxis/documents"))
        store = LocalFileDocumentStore(root)
        repository = LocalFileDocumentRepository(root)
    if os.getenv("PRAXIS_PDF_RENDERER", "").lower() == "weasyprint":
        renderer = WeasyPrintInvoiceRenderer()
    if os.getenv("PRAXIS_OCR_ADAPTER", "").lower() == "tesseract":
        ocr = TesseractInvoiceOcr(languages=os.getenv("PRAXIS_TESSERACT_LANGUAGES", "spa+eng"))
    if store is not None or renderer is not None or ocr is not None:
        set_document_adapters(store, renderer, ocr)
    if repository is not None:
        set_document_repository(repository)

    if engine is not None:
        from app.db.repositories import (
            SqlAlertRuleRepository,
            SqlContractRepository,
            SqlEventRepository,
        )

        if os.getenv("PRAXIS_EVENT_REPOSITORY", "").lower() == "sql":
            set_event_repository(SqlEventRepository(engine))
        if os.getenv("PRAXIS_CONTRACT_REPOSITORY", "").lower() == "sql":
            set_contract_repository(SqlContractRepository(engine))
        if os.getenv("PRAXIS_ALERT_REPOSITORY", "").lower() == "sql":
            set_alert_rule_repository(SqlAlertRuleRepository(engine))

    if os.getenv("PRAXIS_ALERT_NOTIFIER", "").lower() == "smtp":
        host = os.getenv("SMTP_HOST", "")
        if host:
            set_alert_notifier(
                SmtpAlertNotifier(
                    host=host,
                    port=_int("SMTP_PORT", 587),
                    username=os.getenv("SMTP_USER"),
                    password=os.getenv("SMTP_PASSWORD"),
                    sender=os.getenv("SMTP_SENDER", "praxis@localhost"),
                    use_tls=_flag("SMTP_USE_TLS", default=True),
                )
            )
