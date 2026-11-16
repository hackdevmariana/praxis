"""Injectable contract repository for alert scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.context import ToolContext


@dataclass(frozen=True, slots=True)
class ContractRecord:
    id: UUID
    company_id: str
    is_active: bool = True


class ContractRepository(Protocol):
    async def get(self, *, company_id: str, contract_id: UUID) -> ContractRecord | None: ...


class UnconfiguredContractRepository:
    async def get(self, *, company_id: str, contract_id: UUID) -> ContractRecord | None:
        return None


_repository: ContractRepository = UnconfiguredContractRepository()


def get_contract_repository(ctx: ToolContext) -> ContractRepository:
    return _repository


def set_contract_repository(repository: ContractRepository | None) -> None:
    global _repository
    _repository = repository or UnconfiguredContractRepository()
