# tests/conftest.py
"""Shared test fixtures for fastkeel tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config


@pytest.fixture(autouse=True)
def reset_db():
    """Reset DB engine between tests so each test gets a fresh in-memory database."""
    import fastkeel.core.db as db_mod

    db_mod.engine = None
    db_mod.SessionLocal = None
    yield


@pytest.fixture
def raw_config() -> Config:
    """Base test config with in-memory SQLite."""
    return Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret",
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
