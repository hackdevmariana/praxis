"""HTTP helpers translating provider failures into stable tool errors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from app.errors import ErrorCode, ToolError

DEFAULT_TIMEOUT = 10.0


async def _get(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as error:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El proveedor externo no respondió a tiempo.",
        ) from error
    except httpx.HTTPError as error:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "No se pudo contactar con el proveedor externo.",
        ) from error

    if response.status_code == 429:
        raise ToolError(
            ErrorCode.RATE_LIMITED,
            "El proveedor externo ha limitado la petición.",
        )
    if response.status_code >= 400:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            f"El proveedor externo respondió con HTTP {response.status_code}.",
        )
    return response


async def get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """Fetch a URL and decode its JSON body."""
    response = await _get(url, params=params, headers=headers, timeout=timeout)
    try:
        return response.json()
    except ValueError as error:
        raise ToolError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "El proveedor externo devolvió una respuesta no válida.",
        ) from error


async def get_text(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Fetch a URL and return its body as text."""
    response = await _get(url, params=params, headers=headers, timeout=timeout)
    return response.text
