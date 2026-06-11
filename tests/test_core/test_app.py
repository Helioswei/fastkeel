# tests/test_core/test_app.py
from fastapi import FastAPI

from fastkeel.core.config import Config
from fastkeel.core.app import create_app


class TestCreateApp:
    """Test the FastAPI app factory."""

    def test_create_app_returns_fastapi_instance(self):
        config = Config(db_url="sqlite:///:memory:", jwt_secret="test-secret-0123456789abcdef1234")
        app = create_app(config)
        assert isinstance(app, FastAPI)

    def test_app_has_correct_title(self):
        config = Config(
            app_name="test-app",
            db_url="sqlite:///:memory:",
            jwt_secret="test-secret-0123456789abcdef1234",
        )
        app = create_app(config)
        assert app.title == "test-app"

    def test_root_health_check(self):
        from fastapi.testclient import TestClient

        config = Config(
            app_name="test-app",
            db_url="sqlite:///:memory:",
            jwt_secret="test-secret-0123456789abcdef1234",
        )
        app = create_app(config)
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["app"] == "test-app"
