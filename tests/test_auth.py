import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest

from app.auth import (
    ApiKeyRecord,
    ApiKeyStore,
    AuthError,
    AuthSettings,
    InMemoryApiKeyStore,
    authenticate_headers,
    hash_api_key,
    issue_access_token,
    load_api_key_store,
    verify_api_key,
)
from app.context import ToolContext

SECRET = "test-secret-with-at-least-32-characters"
COMPANY = "11111111-1111-4111-8111-111111111111"
SETTINGS = AuthSettings(required=True, jwt_secret=SECRET)


def _token(
    *,
    subject: str = "user-1",
    company_id: str = COMPANY,
    role: str = "admin",
    scopes: list[str] | None = None,
    settings: AuthSettings = SETTINGS,
    expires_in: timedelta | None = None,
) -> str:
    return issue_access_token(
        subject=subject,
        company_id=company_id,
        role=role,
        scopes=scopes or ["finance.calculate", "documents.read"],
        settings=settings,
        expires_in=expires_in,
    )


def _raw_token(payload: dict[str, object]) -> str:
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _claims(**overrides: object) -> dict[str, object]:
    now = int(datetime.now(UTC).timestamp())
    values: dict[str, object] = {
        "sub": "user-1",
        "company_id": COMPANY,
        "role": "admin",
        "scopes": ["finance.calculate"],
        "iat": now,
        "exp": now + 600,
        "iss": "praxis",
        "aud": "praxis-mcp",
    }
    values.update(overrides)
    return values


def _authenticate(
    headers: dict[str, str],
    *,
    settings: AuthSettings = SETTINGS,
    store: ApiKeyStore | None = None,
) -> ToolContext:
    return authenticate_headers(
        headers,
        request_id="req-auth",
        channel="http",
        settings=settings,
        api_key_store=store or InMemoryApiKeyStore(),
    )


def test_auth_enabled_requires_jwt_secret() -> None:
    with pytest.raises(ValueError, match="PRAXIS_JWT_SECRET"):
        AuthSettings(required=True)


def test_only_hs256_is_supported() -> None:
    with pytest.raises(ValueError, match="HS256"):
        AuthSettings(required=True, jwt_secret=SECRET, jwt_algorithm="RS256")


def test_jwt_builds_trusted_context() -> None:
    context = _authenticate(
        {
            "authorization": f"Bearer {_token()}",
            "x-praxis-confirm": "true",
            "x-company-id": "99999999-9999-4999-8999-999999999999",
        }
    )

    assert context.user_id == "user-1"  # type: ignore[attr-defined]
    assert context.company_id == COMPANY  # type: ignore[attr-defined]
    assert context.role == "admin"  # type: ignore[attr-defined]
    assert context.channel == "http"  # type: ignore[attr-defined]
    assert context.confirmed is True  # type: ignore[attr-defined]
    assert context.has_scope("finance.calculate") is True  # type: ignore[attr-defined]
    assert context.has_scope("calendar.write") is False  # type: ignore[attr-defined]


def test_missing_credentials_are_rejected_when_required() -> None:
    with pytest.raises(AuthError) as error:
        _authenticate({})

    assert error.value.code == "authentication_required"


def test_expired_jwt_is_rejected() -> None:
    now = int(datetime.now(UTC).timestamp())
    token = _raw_token(_claims(iat=now - 3600, exp=now - 120))

    with pytest.raises(AuthError) as error:
        _authenticate({"authorization": f"Bearer {token}"})

    assert error.value.code == "invalid_token"


def test_jwt_lifetime_is_capped() -> None:
    now = int(datetime.now(UTC).timestamp())
    token = _raw_token(_claims(iat=now, exp=now + 3600))

    with pytest.raises(AuthError) as error:
        _authenticate({"authorization": f"Bearer {token}"})

    assert error.value.code == "invalid_token"


def test_jwt_with_wrong_audience_is_rejected() -> None:
    token = _raw_token(_claims(aud="otro-servicio"))

    with pytest.raises(AuthError) as error:
        _authenticate({"authorization": f"Bearer {token}"})

    assert error.value.code == "invalid_token"


def test_jwt_with_invalid_company_claim_is_rejected() -> None:
    token = _raw_token(_claims(company_id="not-a-uuid"))

    with pytest.raises(AuthError) as error:
        _authenticate({"authorization": f"Bearer {token}"})

    assert error.value.code == "invalid_token"


def test_malformed_authorization_header_is_rejected() -> None:
    with pytest.raises(AuthError) as error:
        _authenticate({"authorization": "Basic abc"})

    assert error.value.code == "invalid_token"


def test_wildcard_scope_is_not_allowed_in_real_credentials() -> None:
    with pytest.raises(ValueError, match="scope '\\*'"):
        _token(scopes=["*"])


def test_issue_token_rejects_excessive_lifetime() -> None:
    with pytest.raises(ValueError, match="vida"):
        _token(expires_in=timedelta(hours=2))


def test_api_key_authentication() -> None:
    raw_key = "key-1.praxis-live-key-123"
    record = ApiKeyRecord(
        key_id="key-1",
        key_hash=hash_api_key(raw_key),
        user_id="user-2",
        company_id=COMPANY,
        role="manager",
        scopes=frozenset({"documents.write"}),
    )

    context = _authenticate(
        {"x-api-key": raw_key},
        store=InMemoryApiKeyStore([record]),
    )

    assert context.user_id == "user-2"  # type: ignore[attr-defined]
    assert context.role == "manager"  # type: ignore[attr-defined]
    assert context.has_scope("documents.write") is True  # type: ignore[attr-defined]


def test_api_key_hash_is_not_plaintext() -> None:
    raw_key = "key-1.praxis-live-key-123"
    key_hash = hash_api_key(raw_key)

    assert raw_key not in key_hash
    assert key_hash.startswith("$argon2id$")
    assert verify_api_key(raw_key, key_hash) is True
    assert verify_api_key("wrong", key_hash) is False


def test_inactive_api_key_is_rejected() -> None:
    raw_key = "key-1.praxis-live-key-123"
    record = ApiKeyRecord(
        key_id="key-1",
        key_hash=hash_api_key(raw_key),
        user_id="user-2",
        company_id=COMPANY,
        role="manager",
        scopes=frozenset({"documents.write"}),
        is_active=False,
    )

    with pytest.raises(AuthError) as error:
        _authenticate(
            {"x-api-key": raw_key},
            store=InMemoryApiKeyStore([record]),
        )

    assert error.value.code == "invalid_token"


def test_expired_api_key_is_rejected() -> None:
    raw_key = "key-2.praxis-live-key-123"
    record = ApiKeyRecord(
        key_id="key-2",
        key_hash=hash_api_key(raw_key),
        user_id="user-3",
        company_id=COMPANY,
        role="viewer",
        scopes=frozenset({"documents.read"}),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    with pytest.raises(AuthError) as error:
        _authenticate(
            {"x-api-key": raw_key},
            store=InMemoryApiKeyStore([record]),
        )

    assert error.value.code == "invalid_token"


def test_api_key_without_prefix_is_rejected() -> None:
    with pytest.raises(AuthError) as error:
        _authenticate({"x-api-key": "sin-prefijo"})

    assert error.value.code == "invalid_token"


def test_unknown_api_key_is_rejected() -> None:
    raw_key = "key-1.praxis-live-key-123"
    record = ApiKeyRecord(
        key_id="key-1",
        key_hash=hash_api_key(raw_key),
        user_id="user-2",
        company_id=COMPANY,
        role="manager",
        scopes=frozenset({"documents.write"}),
    )

    with pytest.raises(AuthError) as error:
        _authenticate(
            {"x-api-key": "key-1.otra-clave"},
            store=InMemoryApiKeyStore([record]),
        )

    assert error.value.code == "invalid_token"


def test_development_mode_uses_wildcard_scope() -> None:
    context = _authenticate(
        {"x-praxis-confirm": "true"},
        settings=AuthSettings(),
    )

    assert context.company_id is None  # type: ignore[attr-defined]
    assert context.confirmed is True  # type: ignore[attr-defined]
    assert context.has_scope("cualquier.scope") is True  # type: ignore[attr-defined]


def test_api_keys_load_from_file(tmp_path: Path) -> None:
    raw_key = "key-1.praxis-live-key-123"
    path = tmp_path / "api_keys.json"
    path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "key-1",
                        "key_hash": hash_api_key(raw_key),
                        "user_id": "user-2",
                        "company_id": COMPANY,
                        "role": "manager",
                        "scopes": ["documents.read"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    settings = AuthSettings(required=True, jwt_secret=SECRET, api_keys_file=str(path))

    store = load_api_key_store(settings)
    context = _authenticate({"x-api-key": raw_key}, store=store)

    assert context.user_id == "user-2"  # type: ignore[attr-defined]


def test_api_key_file_rejects_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "api_keys.json"
    path.write_text(json.dumps({"keys": "nope"}), encoding="utf-8")
    settings = AuthSettings(required=True, jwt_secret=SECRET, api_keys_file=str(path))

    with pytest.raises(ValueError, match="lista"):
        load_api_key_store(settings)
