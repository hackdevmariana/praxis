import asyncio
from datetime import UTC, datetime
from email.message import EmailMessage

import pytest

from app.context import ToolContext
from app.providers.alerts import (
    AlertEventRecord,
    AlertMessage,
    AlertRuleRecord,
    SmtpAlertNotifier,
    set_alert_rule_repository,
)
from app.providers.contracts import ContractRecord
from app.tools.alerts.contract_renewal.schemas import ContractRenewalInput
from app.tools.alerts.contract_renewal.tool import schedule_contract_renewal
from tests.test_alerts_contract_renewal import CONTRACT_ID, install_repository

COMPANY_ID = "company-1"


class FakeSmtp:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []
        self.started_tls = False

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        return None

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


class RecordingRuleRepository:
    def __init__(self) -> None:
        self.rules: list[AlertRuleRecord] = []
        self.events: list[AlertEventRecord] = []

    async def save(self, rule: AlertRuleRecord, events: tuple[AlertEventRecord, ...]) -> None:
        self.rules.append(rule)
        self.events.extend(events)


def test_smtp_notifier_sends_email(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSmtp()

    def smtp_factory(_host: str, _port: int) -> FakeSmtp:
        return fake

    monkeypatch.setattr("app.providers.alerts.smtplib.SMTP", smtp_factory)
    notifier = SmtpAlertNotifier(host="smtp.example.com", sender="avisos@example.com")

    asyncio.run(
        notifier.send(
            AlertMessage(
                company_id=COMPANY_ID,
                contract_id=CONTRACT_ID,
                recipient="ana@example.com",
                subject="Aviso",
                body="El contrato se renueva pronto.",
                trigger_at=datetime(2027, 1, 1, tzinfo=UTC),
            )
        )
    )

    assert fake.started_tls is True
    assert len(fake.messages) == 1
    assert fake.messages[0]["To"] == "ana@example.com"
    assert "renueva" in fake.messages[0].get_content()


def test_schedule_persists_rule_and_events() -> None:
    install_repository(ContractRecord(id=CONTRACT_ID, company_id=COMPANY_ID))
    repository = RecordingRuleRepository()
    set_alert_rule_repository(repository)

    result = asyncio.run(
        schedule_contract_renewal(
            ContractRenewalInput.model_validate(
                {
                    "contract_id": str(CONTRACT_ID),
                    "renewal_date": "2028-03-31",
                    "notice_days": [60, 30],
                    "channel": "none",
                    "idempotency_key": "renovacion-2028",
                }
            ),
            ToolContext(request_id="test", company_id=COMPANY_ID, confirmed=True),
        )
    )

    assert result.metadata_extra["alert_rule_id"] == result.data.alert_rule_id
    assert result.metadata_extra["notifications_sent"] == 0
    assert len(repository.rules) == 1
    assert [event.days_before for event in repository.events] == [60, 30]
