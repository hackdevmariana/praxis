"""API key and JWT authentication for REST and MCP channels."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.context import ToolContext
from app.errors import ErrorCode, ToolError

_ROLES = frozenset({"owner", "admin", "manager", "viewer", "employee", "association_admin"})
_PUBLIC_PATHS = frozenset({"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})
_CURRENT_CONTEXT: ContextVar[ToolContext | None] = ContextVar("praxis_tool_context", default=None)
_HASHER = PasswordHasher()


class AuthError(Exception):
    """Authentication failure that maps to an HTTP 401 response."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(frozen=True, slots=True)
class AuthSettings:
    """Runtime authentication configuration."""

    required: bool = False
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "praxis"
    jwt_audience: str = "praxis-mcp"
    jwt_expires_in: timedelta = timedelta(minutes=30)
    api_keys_file: str | None = None

    def __post_init__(self) -> None:
        if self.jwt_algorithm != "HS256":
            raise ValueError("Solo se admite HS256 en el MVP")
        if self.jwt_secret is not None and len(self.jwt_secret) < 32:
            raise ValueError("PRAXIS_JWT_SECRET debe tener al menos 32 caracteres")
        if self.required and not self.jwt_secret:
            raise ValueError("PRAXIS_JWT_SECRET es obligatorio cuando PRAXIS_AUTH_REQUIRED=true")
        if self.jwt_expires_in <= timedelta(0):
            raise ValueError("PRAXIS_JWT_EXPIRES_MINUTES debe ser positivo")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AuthSettings:
        values = os.environ if env is None else env
        secret = values.get("PRAXIS_JWT_SECRET") or values.get("PRAXIS_SECRET_KEY")
        minutes = int(values.get("PRAXIS_JWT_EXPIRES_MINUTES", "30"))
        return cls(
            required=_truthy(values.get("PRAXIS_AUTH_REQUIRED", "false")),
            jwt_secret=secret,
            jwt_algorithm=values.get("PRAXIS_JWT_ALGORITHM", "HS256"),
            jwt_issuer=values.get("PRAXIS_JWT_ISSUER", "praxis"),
            jwt_audience=values.get("PRAXIS_JWT_AUDIENCE", "praxis-mcp"),
            jwt_expires_in=timedelta(minutes=minutes),
            api_keys_file=values.get("PRAXIS_API_KEYS_FILE") or None,
        )


@dataclass(frozen=True, slots=True)
class ApiKeyRecord:
    """Stored API key metadata. Only the Argon2id hash is persisted."""

    key_id: str
    key_hash: str
    user_id: str
    company_id: str
    role: str
    scopes: frozenset[str]
    expires_at: datetime | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        _text(self.key_id, "key_id")
        if "." in self.key_id:
            raise ValueError("key_id no puede contener puntos")
        if not self.key_hash:
            raise ValueError("key_hash es obligatorio")
        _uuid_text(self.company_id, "company_id")
        if "*" in self.scopes:
            raise ValueError("El scope '*' no está permitido en API keys")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ApiKeyRecord:
        key_id = _text(data.get("key_id"), "key_id")
        if "." in key_id:
            raise ValueError("key_id no puede contener puntos")
        scopes = _scopes(data.get("scopes"))
        expires_at = data.get("expires_at")
        if expires_at is not None:
            if not isinstance(expires_at, str):
                raise ValueError("expires_at debe ser una fecha ISO 8601")
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            expires_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        is_active = data.get("is_active", True)
        if not isinstance(is_active, bool):
            raise ValueError("is_active debe ser booleano")
        return cls(
            key_id=key_id,
            key_hash=_text(data.get("key_hash"), "key_hash"),
            user_id=_text(data.get("user_id"), "user_id"),
            company_id=_uuid_text(data.get("company_id"), "company_id"),
            role=_role(data.get("role")),
            scopes=scopes,
            expires_at=expires_at,
            is_active=is_active,
        )


class ApiKeyStore:
    """Minimal API key store; replaceable by a database-backed repository."""

    def get(self, key_id: str) -> ApiKeyRecord | None:
        raise NotImplementedError


class InMemoryApiKeyStore(ApiKeyStore):
    def __init__(self, records: Sequence[ApiKeyRecord] = ()) -> None:
        self._records = {record.key_id: record for record in records}

    def get(self, key_id: str) -> ApiKeyRecord | None:
        return self._records.get(key_id)


def hash_api_key(raw_key: str) -> str:
    """Hash a plaintext API key for storage or configuration."""
    if not raw_key:
        raise ValueError("La API key no puede estar vacía")
    return _HASHER.hash(raw_key)


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    try:
        return _HASHER.verify(key_hash, raw_key)
    except (VerificationError, InvalidHashError, ValueError):
        return False


def load_api_key_store(settings: AuthSettings) -> ApiKeyStore:
    if not settings.api_keys_file:
        return InMemoryApiKeyStore()
    path = Path(settings.api_keys_file)
    data: object = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = cast(dict[str, object], data).get("keys")
    if not isinstance(data, list):
        raise ValueError("PRAXIS_API_KEYS_FILE debe contener una lista de claves")
    records: list[ApiKeyRecord] = []
    for item in cast(list[object], data):
        if isinstance(item, dict):
            records.append(ApiKeyRecord.from_dict(cast(Mapping[str, Any], item)))
    return InMemoryApiKeyStore(records)


def issue_access_token(
    *,
    subject: str,
    company_id: str,
    role: str,
    scopes: Sequence[str],
    settings: AuthSettings,
    expires_in: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    """Issue a short-lived HS256 token for a user session."""
    if not settings.jwt_secret:
        raise ValueError("No hay secreto JWT configurado")
    lifetime = expires_in or settings.jwt_expires_in
    if lifetime <= timedelta(0) or lifetime > settings.jwt_expires_in:
        raise ValueError("La vida del token debe estar entre 1 segundo y el máximo")
    issued_at = now or datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": _text(subject, "sub"),
        "company_id": _uuid_text(company_id, "company_id"),
        "role": _role(role),
        "scopes": sorted(_scopes(scopes)),
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + lifetime).timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def authenticate_headers(
    headers: Mapping[str, str],
    *,
    request_id: str,
    channel: str,
    settings: AuthSettings,
    api_key_store: ApiKeyStore,
) -> ToolContext:
    """Build a trusted execution context from HTTP headers."""
    normalized = {key.lower(): value for key, value in headers.items()}
    confirmed = _truthy(normalized.get("x-praxis-confirm", "false"))
    authorization = normalized.get("authorization")
    api_key = normalized.get("x-api-key")

    if not settings.required and not authorization and not api_key:
        return _development_context(request_id, channel, confirmed)

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthError(
                ErrorCode.INVALID_TOKEN,
                "La cabecera Authorization debe usar el esquema Bearer.",
            )
        claims = _decode_token(token, settings)
        return ToolContext(
            request_id=request_id,
            user_id=claims.user_id,
            company_id=claims.company_id,
            role=claims.role,
            channel=channel,
            scopes=claims.scopes,
            confirmed=confirmed,
        )

    if api_key:
        record = _authenticate_api_key(api_key, api_key_store)
        return ToolContext(
            request_id=request_id,
            user_id=record.user_id,
            company_id=record.company_id,
            role=record.role,
            channel=channel,
            scopes=record.scopes,
            confirmed=confirmed,
        )

    raise AuthError(
        ErrorCode.AUTHENTICATION_REQUIRED,
        "Faltan credenciales: Authorization Bearer o X-API-Key.",
    )


def current_context() -> ToolContext | None:
    return _CURRENT_CONTEXT.get()


def fallback_context(
    settings: AuthSettings,
    *,
    request_id: str,
    channel: str,
    confirmed: bool = False,
) -> ToolContext:
    """Context for in-process transports without an HTTP authentication layer."""
    if settings.required:
        raise ToolError(
            ErrorCode.AUTHENTICATION_REQUIRED,
            "La petición no pasó por la capa de autenticación.",
        )
    return _development_context(request_id, channel, confirmed)


class AuthMiddleware:
    """Authenticate HTTP requests and expose the context to the tool runtime."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: AuthSettings,
        api_key_store: ApiKeyStore,
    ) -> None:
        self.app = app
        self.settings = settings
        self.api_key_store = api_key_store

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = request.url.path
        if path in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        request_id = request.headers.get("x-request-id") or uuid4().hex
        channel = "http" if path.startswith("/api/") else "mcp"
        try:
            context = authenticate_headers(
                dict(request.headers),
                request_id=request_id,
                channel=channel,
                settings=self.settings,
                api_key_store=self.api_key_store,
            )
        except AuthError as error:
            response = JSONResponse(
                status_code=401,
                content={"success": False, "error": error.to_dict()},
            )
            await response(scope, receive, send)
            return

        token = _CURRENT_CONTEXT.set(context)
        try:
            await self.app(scope, receive, send)
        finally:
            _CURRENT_CONTEXT.reset(token)


@dataclass(frozen=True, slots=True)
class _TokenClaims:
    user_id: str
    company_id: str
    role: str
    scopes: frozenset[str]


def _decode_token(token: str, settings: AuthSettings) -> _TokenClaims:
    if not settings.jwt_secret:
        raise AuthError(
            ErrorCode.INVALID_TOKEN,
            "La autenticación JWT no está configurada.",
        )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=60,
            options={
                "require": [
                    "sub",
                    "company_id",
                    "role",
                    "scopes",
                    "iat",
                    "exp",
                    "iss",
                    "aud",
                ]
            },
        )
    except jwt.ExpiredSignatureError as error:
        raise AuthError(ErrorCode.INVALID_TOKEN, "El token ha caducado.") from error
    except jwt.InvalidTokenError as error:
        raise AuthError(ErrorCode.INVALID_TOKEN, "El token no es válido.") from error

    issued_at = _timestamp(payload.get("iat"))
    expires_at = _timestamp(payload.get("exp"))
    now = int(datetime.now(UTC).timestamp())
    if issued_at > now + 60 or expires_at <= issued_at:
        raise AuthError(ErrorCode.INVALID_TOKEN, "El token tiene fechas inválidas.")
    if expires_at - issued_at > settings.jwt_expires_in.total_seconds():
        raise AuthError(
            ErrorCode.INVALID_TOKEN,
            "El token supera la vida máxima configurada.",
        )

    try:
        return _TokenClaims(
            user_id=_text(payload.get("sub"), "sub"),
            company_id=_uuid_text(payload.get("company_id"), "company_id"),
            role=_role(payload.get("role")),
            scopes=_scopes(payload.get("scopes")),
        )
    except ValueError as error:
        raise AuthError(ErrorCode.INVALID_TOKEN, "El token contiene claims inválidos.") from error


def _authenticate_api_key(raw_key: str, store: ApiKeyStore) -> ApiKeyRecord:
    key_id, separator, _secret = raw_key.partition(".")
    if not separator:
        raise AuthError(
            ErrorCode.INVALID_TOKEN,
            "La API key debe tener el formato <key_id>.<secret>.",
        )
    record = store.get(key_id)
    if record is None or not record.is_active:
        raise AuthError(ErrorCode.INVALID_TOKEN, "La API key no es válida.")
    if record.expires_at is not None and record.expires_at <= datetime.now(UTC):
        raise AuthError(ErrorCode.INVALID_TOKEN, "La API key ha caducado.")
    if not verify_api_key(raw_key, record.key_hash):
        raise AuthError(ErrorCode.INVALID_TOKEN, "La API key no es válida.")
    return record


def _development_context(request_id: str, channel: str, confirmed: bool) -> ToolContext:
    return ToolContext(
        request_id=request_id,
        channel=channel,
        scopes=frozenset({"*"}),
        confirmed=confirmed,
    )


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _scopes(raw: object) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list | tuple | set | frozenset):
        values = list(cast(Sequence[object], raw))
    else:
        raise ValueError("scopes debe ser una lista de strings")
    scopes: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("scopes contiene un valor inválido")
        scope = value.strip()
        if scope == "*":
            raise ValueError("El scope '*' no está permitido en credenciales reales")
        scopes.add(scope)
    return frozenset(scopes)


def _text(raw: object, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field} es obligatorio")
    return raw.strip()


def _uuid_text(raw: object, field: str) -> str:
    value = _text(raw, field)
    try:
        return str(UUID(value))
    except ValueError as error:
        raise ValueError(f"{field} debe ser un UUID") from error


def _role(raw: object) -> str:
    role = _text(raw, "role")
    if role not in _ROLES:
        raise ValueError(f"Rol no permitido: {role}")
    return role


def _timestamp(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise AuthError(ErrorCode.INVALID_TOKEN, "El token no contiene iat/exp válidos.")
    return int(raw)
