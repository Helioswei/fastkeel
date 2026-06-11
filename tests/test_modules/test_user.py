# tests/test_modules/test_user.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config
from fastkeel.modules import include_user


@pytest.fixture
def user_app() -> FastAPI:
    """App with user module enabled."""
    config = Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret",
        debug=True,
    )
    app = create_app(config)
    include_user(app, config)
    return app


@pytest.fixture
def user_client(user_app: FastAPI) -> TestClient:
    with TestClient(user_app) as c:
        yield c


class TestRegister:
    """POST /api/v1/auth/register"""

    def test_register_success(self, user_client):
        response = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "device-001"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "token" in body
        assert "user" in body
        assert body["user"]["device_id"] == "device-001"
        assert body["user"]["nickname"] == ""
        assert body["user"]["is_active"] is True
        assert "id" in body["user"]

    def test_register_returns_jwt(self, user_client):
        response = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "device-002"},
        )
        token = response.json()["token"]
        assert token.count(".") == 2  # JWT format

    def test_register_duplicate_device_id_returns_existing(self, user_client):
        """Re-registering same device_id returns existing user + new token."""
        first = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "dup-device"},
        )
        second = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "dup-device"},
        )
        assert second.status_code == 200
        assert second.json()["user"]["id"] == first.json()["user"]["id"]
        assert second.json()["token"] != first.json()["token"]

    def test_register_missing_device_id_returns_422(self, user_client):
        response = user_client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login"""

    def test_login_success(self, user_client):
        reg = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "login-device"},
        )
        user_id = reg.json()["user"]["id"]

        response = user_client.post(
            "/api/v1/auth/login",
            json={"device_id": "login-device"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "token" in body
        assert body["user"]["id"] == user_id

    def test_login_unregistered_device_returns_404(self, user_client):
        response = user_client.post(
            "/api/v1/auth/login",
            json={"device_id": "never-registered"},
        )
        assert response.status_code == 404

    def test_login_returns_new_token(self, user_client):
        reg = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "token-test"},
        )
        register_token = reg.json()["token"]

        login = user_client.post(
            "/api/v1/auth/login",
            json={"device_id": "token-test"},
        )
        login_token = login.json()["token"]
        assert login_token != register_token


class TestGetMe:
    """GET /api/v1/auth/me"""

    def test_get_me_with_valid_token(self, user_client):
        reg = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "me-device"},
        )
        token = reg.json()["token"]

        response = user_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["device_id"] == "me-device"

    def test_get_me_without_token_returns_401(self, user_client):
        response = user_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self, user_client):
        response = user_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401


class TestUpdateMe:
    """PATCH /api/v1/auth/me"""

    def test_update_nickname(self, user_client):
        reg = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "update-device"},
        )
        token = reg.json()["token"]

        response = user_client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"nickname": "新昵称"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["nickname"] == "新昵称"

    def test_update_avatar(self, user_client):
        reg = user_client.post(
            "/api/v1/auth/register",
            json={"device_id": "avatar-device"},
        )
        token = reg.json()["token"]

        response = user_client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"avatar_url": "https://example.com/avatar.png"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["avatar_url"] == "https://example.com/avatar.png"

    def test_update_requires_auth(self, user_client):
        response = user_client.patch(
            "/api/v1/auth/me",
            json={"nickname": "hacker"},
        )
        assert response.status_code == 401
