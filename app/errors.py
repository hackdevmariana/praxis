"""Tool errors and MCP error codes."""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Standard error codes exposed over MCP."""

    INVALID_PARAMS = "invalid_params"
    AUTHENTICATION_REQUIRED = "authentication_required"
    INVALID_TOKEN = "invalid_token"
    PERMISSION_DENIED = "permission_denied"
    TOOL_NOT_AVAILABLE = "tool_not_available"
    CONFIRMATION_REQUIRED = "confirmation_required"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


class ToolError(Exception):
    """A controlled tool failure with a stable, machine-readable code."""

    def __init__(
        self,
        code: str | ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload
