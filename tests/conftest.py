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
    except ImportError:
        pass
    yield


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
