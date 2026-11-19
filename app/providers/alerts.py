from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from datetime import date, datetime
from email.message import EmailMessage
from typing import Protocol
from uuid import UUID

from app.context import ToolContext
from app.errors import ErrorCode, ToolError


@dataclass(frozen=True, slots=True)
class AlertRuleRecord:
    id: UUID
    company_id: str
    contract_id: UUID
    renewal_date: date
    channel: str
    next_trigger_at: datetime | None
    idempotency_key: str | None


@dataclass(frozen=True, slots=True)
class AlertEventRecord:
    id: UUID
    company_id: str
    alert_rule_id: UUID
    days_before: int
    trigger_at: datetime
    channel: str
    status: str


@dataclass(frozen=True, slots=True)
class AlertMessage:
    company_id: str
    contract_id: UUID
    recipient: str
    subject: str
    body: str
    trigger_at: datetime


class AlertRuleRepository(Protocol):
    async def save(self, rule: AlertRuleRecord, events: tuple[AlertEventRecord, ...]) -> None: ...


class AlertNotifier(Protocol):
    async def send(self, message: AlertMessage) -> None: ...


class NoopAlertRuleRepository:
    async def save(self, rule: AlertRuleRecord, events: tuple[AlertEventRecord, ...]) -> None:
        return None


class NoopAlertNotifier:
    async def send(self, message: AlertMessage) -> None:
        return None


class SmtpAlertNotifier:
    """Notificador SMTP real, con envío diferido al hilo de E/S."""

    def __init__(
        self,
        *,
        host: str,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        sender: str = "praxis@localhost",
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender
        self.use_tls = use_tls

    async def send(self, message: AlertMessage) -> None:
        if not self.host:
            raise ToolError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "SMTP no está configurado para este despliegue.",
            )
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: AlertMessage) -> None:
        email = EmailMessage()
        email["From"] = self.sender
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email.set_content(message.body)
        with smtplib.SMTP(self.host, self.port) as client:
            if self.use_tls:
                client.starttls()
            if self.username and self.password:
                client.login(self.username, self.password)
            client.send_message(email)


_repository: AlertRuleRepository = NoopAlertRuleRepository()
_notifier: AlertNotifier = NoopAlertNotifier()


def get_alert_rule_repository(ctx: ToolContext) -> AlertRuleRepository:
    return _repository


def set_alert_rule_repository(repository: AlertRuleRepository | None) -> None:
    global _repository
    _repository = repository or NoopAlertRuleRepository()


def get_alert_notifier(ctx: ToolContext) -> AlertNotifier:
    return _notifier


def set_alert_notifier(notifier: AlertNotifier | None) -> None:
    global _notifier
    _notifier = notifier or NoopAlertNotifier()
