"""Injectable repository for contract renewals and their notice periods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.context import ToolContext
from app.errors import ErrorCode, ToolError


@dataclass(frozen=True, slots=True)
class RenewalRecord:
    contract_id: str
    supplier: str
    category: str
    renewal_date: date
    notice_days: tuple[int, ...]
    estimated_annual_cost: Decimal | None


class RenewalRepository(Protocol):
    async def list_for_company(self, *, company_id: str) -> list[RenewalRecord]: ...


class UnconfiguredRenewalRepository:
    async def list_for_company(self, *, company_id: str) -> list[RenewalRecord]:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El repositorio de renovaciones no está configurado.",
        )


_repository: RenewalRepository = UnconfiguredRenewalRepository()


def get_renewal_repository(ctx: ToolContext) -> RenewalRepository:
    return _repository


def set_renewal_repository(repository: RenewalRepository | None) -> None:
    global _repository
    _repository = repository or UnconfiguredRenewalRepository()
