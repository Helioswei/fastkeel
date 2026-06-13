# tests/conftest.py
"""Shared test fixtures for fastkeel tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config


@pytest.fixture(autouse=True)
def reset_db():
    """Reset DB engine and module-level configs between tests."""
    import fastkeel.core.db as db_mod

    db_mod.engine = None
    db_mod.SessionLocal = None
    # Reset user module config
    import fastkeel.modules.user as user_mod

    user_mod._user_config = None
    # Reset social module config (if module exists)
    try:
        import fastkeel.modules.social as social_mod

        social_mod._social_config = None
    except ImportError:
        pass
    # Reset payment module config (if module exists)
    try:
        import fastkeel.modules.payment as payment_mod

        payment_mod._payment_config = None
        payment_mod.receipt_verifiers.clear()
        payment_mod.webhook_parsers.clear()
        # Re-register built-in dev verifier
        payment_mod.register_verifier("dev", lambda r: payment_mod._dev_verify(r))
        payment_mod.register_webhook_parser("dev", lambda b, h: payment_mod._dev_parse_webhook(b, h))
    except ImportError:
        pass
    # Reset auth module config
    import fastkeel.core.auth as auth_mod

    auth_mod._config_dependency_instance = None
    yield


def register_user(client, device_id: str = "test-device") -> tuple[str, str]:
    """Helper: register a device and return (token, user_id)."""
    resp = client.post("/api/v1/auth/register", json={"device_id": device_id})
    data = resp.json()
    return data["token"], data["user"]["id"]


@pytest.fixture
def raw_config() -> Config:
    """Base test config with in-memory SQLite."""
    return Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret-0123456789abcdef1234",
        debug=True,
    )


@pytest.fixture
def app(raw_config: Config) -> FastAPI:
    """Create a minimal FastAPI app without any modules."""
    return create_app(raw_config)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c
