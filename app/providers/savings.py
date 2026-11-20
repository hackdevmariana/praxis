"""Injectable repository for the tenant savings ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.context import ToolContext
from app.errors import ErrorCode, ToolError


@dataclass(frozen=True, slots=True)
class SavingsEntryRecord:
    id: str
    company_id: str
    entry_date: date
    category: str
    supplier: str | None
    description: str
    baseline_cost: Decimal
    actual_cost: Decimal
    annualized_savings: Decimal
    status: str


class SavingsRepository(Protocol):
    async def list_for_company(
        self, *, company_id: str, period_start: date, period_end: date
    ) -> list[SavingsEntryRecord]: ...


class UnconfiguredSavingsRepository:
    async def list_for_company(
        self, *, company_id: str, period_start: date, period_end: date
    ) -> list[SavingsEntryRecord]:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El repositorio de ahorros no está configurado.",
        )


_repository: SavingsRepository = UnconfiguredSavingsRepository()


def get_savings_repository(ctx: ToolContext) -> SavingsRepository:
    return _repository


def set_savings_repository(repository: SavingsRepository | None) -> None:
    global _repository
    _repository = repository or UnconfiguredSavingsRepository()
