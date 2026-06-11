# tests/test_integration.py
"""End-to-end integration tests for the full user auth flow."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config
from fastkeel.modules import include_user, include_social


@pytest.fixture
def full_app() -> FastAPI:
    config = Config(
        db_url="sqlite:///:memory:",
        jwt_secret="integration-test-secret-0123456!",
        debug=True,
    )
    app = create_app(config)
    include_user(app, config)
    return app


@pytest.fixture
def client(full_app: FastAPI) -> TestClient:
    with TestClient(full_app) as c:
        yield c


class TestSocialIntegration:
    """Social module integrated with user auth."""

    @pytest.fixture
    def full_app(self) -> FastAPI:
        config = Config(
            db_url="sqlite:///:memory:",
            jwt_secret="integration-test-secret-0123456!",
            debug=True,
            social_enable_groups=True,
        )
        app = create_app(config)
        include_user(app, config)
        include_social(app, config)
        return app

    @pytest.fixture
    def client(self, full_app):
        with TestClient(full_app) as c:
            yield c

    def test_full_social_flow(self, client):
        """Register two users -> invite -> bind -> get buddy -> remove."""
        alice = client.post("/api/v1/auth/register", json={"device_id": "social-alice"}).json()
        bob = client.post("/api/v1/auth/register", json={"device_id": "social-bob"}).json()
        alice_token = alice["token"]
        bob_token = bob["token"]

        invite = client.post(
            "/api/v1/social/invite",
            headers={"Authorization": f"Bearer {alice_token}"},
        ).json()
        code = invite["invite_code"]

        bind = client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )
        assert bind.status_code == 200

        alice_buddy = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {alice_token}"},
        ).json()
        assert alice_buddy["buddy"]["id"] == bob["user"]["id"]

        client.delete(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {bob_token}"},
        )

        alice_buddy = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {alice_token}"},
        ).json()
        assert alice_buddy["buddy"] is None

    def test_group_flow(self, client):
        """Register two users -> create group -> join -> get -> delete."""
        alice = client.post("/api/v1/auth/register", json={"device_id": "group-alice"}).json()
        bob = client.post("/api/v1/auth/register", json={"device_id": "group-bob"}).json()

        create = client.post(
            "/api/v1/social/groups",
            headers={"Authorization": f"Bearer {alice['token']}"},
            json={"name": "集成测试小组"},
        ).json()
        group_id = create["id"]

        client.post(
            "/api/v1/social/groups/join",
            headers={"Authorization": f"Bearer {bob['token']}"},
            json={"invite_code": create["invite_code"]},
        )

        get = client.get(f"/api/v1/social/groups/{group_id}").json()
        assert len(get["members"]) == 2

        client.delete(
            f"/api/v1/social/groups/{group_id}",
            headers={"Authorization": f"Bearer {alice['token']}"},
        )

        assert client.get(f"/api/v1/social/groups/{group_id}").status_code == 404


class TestFullAuthFlow:
    """Complete auth lifecycle: register -> me -> update -> login -> me again."""

    def test_register_then_get_me(self, client):
        """Register a device and immediately retrieve its info."""
        reg = client.post("/api/v1/auth/register", json={"device_id": "flow-device"})
        assert reg.status_code == 200
        reg_data = reg.json()
        user_id = reg_data["user"]["id"]
        token = reg_data["token"]

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        assert me.json()["id"] == user_id
        assert me.json()["device_id"] == "flow-device"

    def test_register_update_login_cycle(self, client):
        """Register -> update -> login again -> verify updated fields."""
        # Register
        reg = client.post("/api/v1/auth/register", json={"device_id": "cycle-device"})
        token1 = reg.json()["token"]

        # Update nickname
        update = client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token1}"},
            json={"nickname": "循环测试"},
        )
        assert update.status_code == 200
        assert update.json()["nickname"] == "循环测试"

        # Login again
        login = client.post("/api/v1/auth/login", json={"device_id": "cycle-device"})
        assert login.status_code == 200
        token2 = login.json()["token"]
        assert token2 != token1  # new JWT

        # Verify updated fields persist after login
        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert me.json()["nickname"] == "循环测试"
        assert me.json()["device_id"] == "cycle-device"

    def test_protected_routes_all_require_auth(self, client):
        """All protected endpoints should return 401 without token."""
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.patch("/api/v1/auth/me", json={}).status_code == 401

    def test_health_check_works_with_app(self, client):
        """Health check endpoint at / should work."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
