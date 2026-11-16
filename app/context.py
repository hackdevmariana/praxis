"""Execution context carried through every tool call."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Identity and request data resolved from the caller's credentials."""

    request_id: str
    user_id: str | None = None
    company_id: str | None = None
    role: str | None = None
    channel: str = "mcp"
    scopes: frozenset[str] = field(default_factory=lambda: frozenset[str]())
    confirmed: bool = False
    allowed_tools: frozenset[str] | None = None

    def has_scope(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes
