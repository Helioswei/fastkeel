# tests/test_modules/test_social.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config
from fastkeel.modules import include_user, include_social


@pytest.fixture
def app_with_social() -> FastAPI:
    config = Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret",
        debug=True,
        social_enable_groups=True,
    )
    app = create_app(config)
    include_user(app, config)
    include_social(app, config)
    return app


@pytest.fixture
def client(app_with_social):
    with TestClient(app_with_social) as c:
        yield c


def _register(client, device_id):
    """Helper: register a device and return (token, user_id)."""
    resp = client.post("/api/v1/auth/register", json={"device_id": device_id})
    data = resp.json()
    return data["token"], data["user"]["id"]


class TestBuddy:
    """Test buddy invite/bind/get/remove flow."""

    def test_invite_returns_code(self, client):
        token, _ = _register(client, "alice")
        resp = client.post("/api/v1/social/invite", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert "invite_code" in body
        assert len(body["invite_code"]) >= 4

    def test_invite_requires_auth(self, client):
        resp = client.post("/api/v1/social/invite")
        assert resp.status_code == 401

    def test_invite_generates_unique_codes(self, client):
        token, _ = _register(client, "unique-test")
        resp1 = client.post("/api/v1/social/invite", headers={"Authorization": f"Bearer {token}"})
        resp2 = client.post("/api/v1/social/invite", headers={"Authorization": f"Bearer {token}"})
        assert resp1.json()["invite_code"] != resp2.json()["invite_code"]

    def test_complete_buddy_flow(self, client):
        """Alice invites -> Bob binds -> both can see each other -> Alice unbinds."""
        alice_token, alice_id = _register(client, "alice-flow")
        bob_token, bob_id = _register(client, "bob-flow")

        invite_resp = client.post(
            "/api/v1/social/invite",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        code = invite_resp.json()["invite_code"]

        bind_resp = client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )
        assert bind_resp.status_code == 200
        assert bind_resp.json()["status"] == "active"

        alice_buddy = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert alice_buddy.status_code == 200
        assert alice_buddy.json()["buddy"]["id"] == bob_id

        bob_buddy = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_buddy.status_code == 200
        assert bob_buddy.json()["buddy"]["id"] == alice_id

    def test_double_bind_returns_404(self, client):
        alice_token, _ = _register(client, "alice-double")
        bob_token, _ = _register(client, "bob-double")

        invite = client.post(
            "/api/v1/social/invite",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        code = invite.json()["invite_code"]

        client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )

        retry = client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )
        assert retry.status_code == 404

    def test_bind_invalid_code_returns_404(self, client):
        token, _ = _register(client, "bob-invalid")
        resp = client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {token}"},
            json={"invite_code": "invalid123"},
        )
        assert resp.status_code == 404

    def test_bind_requires_auth(self, client):
        resp = client.post("/api/v1/social/bind", json={"invite_code": "xxx"})
        assert resp.status_code == 401

    def test_buddy_without_buddy_returns_null(self, client):
        token, _ = _register(client, "lonely")
        resp = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["buddy"] is None

    def test_buddy_requires_auth(self, client):
        resp = client.get("/api/v1/social/buddy")
        assert resp.status_code == 401

    def test_delete_buddy(self, client):
        alice_token, _ = _register(client, "alice-del")
        bob_token, _ = _register(client, "bob-del")

        invite = client.post(
            "/api/v1/social/invite",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        code = invite.json()["invite_code"]

        client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )

        del_resp = client.delete(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert del_resp.status_code == 200

        alice_buddy = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert alice_buddy.json()["buddy"] is None

    def test_delete_buddy_requires_auth(self, client):
        resp = client.delete("/api/v1/social/buddy")
        assert resp.status_code == 401


class TestGroup:
    """Test group CRUD flow."""

    def test_create_group(self, client):
        token, alice_id = _register(client, "alice-group")
        resp = client.post(
            "/api/v1/social/groups",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "测试小组"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "测试小组"
        assert "id" in body
        assert "invite_code" in body
        assert body["owner_id"] == alice_id

    def test_create_group_requires_auth(self, client):
        resp = client.post("/api/v1/social/groups", json={"name": "hacker"})
        assert resp.status_code == 401

    def test_join_group(self, client):
        alice_token, _ = _register(client, "alice-gjoin")
        bob_token, _ = _register(client, "bob-gjoin")

        create = client.post(
            "/api/v1/social/groups",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"name": "共同小组"},
        )
        code = create.json()["invite_code"]

        join = client.post(
            "/api/v1/social/groups/join",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )
        assert join.status_code == 200
        assert join.json()["role"] == "member"

    def test_join_invalid_code_returns_404(self, client):
        token, _ = _register(client, "bogus-join")
        resp = client.post(
            "/api/v1/social/groups/join",
            headers={"Authorization": f"Bearer {token}"},
            json={"invite_code": "bad-code"},
        )
        assert resp.status_code == 404

    def test_get_group(self, client):
        alice_token, alice_id = _register(client, "alice-gget")
        bob_token, _ = _register(client, "bob-gget")

        create = client.post(
            "/api/v1/social/groups",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"name": "可见小组"},
        )
        group_id = create.json()["id"]
        code = create.json()["invite_code"]

        client.post(
            "/api/v1/social/groups/join",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )

        get = client.get(f"/api/v1/social/groups/{group_id}")
        assert get.status_code == 200
        body = get.json()
        assert body["name"] == "可见小组"
        assert len(body["members"]) == 2

    def test_get_group_not_found(self, client):
        resp = client.get("/api/v1/social/groups/nonexistent")
        assert resp.status_code == 404

    def test_delete_group_by_owner(self, client):
        alice_token, _ = _register(client, "alice-gdel")
        bob_token, _ = _register(client, "bob-gdel")

        create = client.post(
            "/api/v1/social/groups",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"name": "可删小组"},
        )
        group_id = create.json()["id"]
        code = create.json()["invite_code"]

        client.post(
            "/api/v1/social/groups/join",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )

        resp = client.delete(
            f"/api/v1/social/groups/{group_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200

        get = client.get(f"/api/v1/social/groups/{group_id}")
        assert get.status_code == 404

    def test_delete_group_by_non_owner_returns_403(self, client):
        alice_token, _ = _register(client, "alice-gforbid")
        bob_token, _ = _register(client, "bob-gforbid")

        create = client.post(
            "/api/v1/social/groups",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"name": "禁止删除"},
        )
        group_id = create.json()["id"]

        resp = client.delete(
            f"/api/v1/social/groups/{group_id}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert resp.status_code == 403


class TestGroupsDisabled:
    """Test that group routes are not registered when social_enable_groups=False."""

    @pytest.fixture
    def app_no_groups(self) -> FastAPI:
        config = Config(
            db_url="sqlite:///:memory:",
            jwt_secret="test-secret",
            debug=True,
            social_enable_groups=False,
        )
        app = create_app(config)
        include_user(app, config)
        include_social(app, config)
        return app

    @pytest.fixture
    def no_group_client(self, app_no_groups):
        with TestClient(app_no_groups) as c:
            yield c

    def test_group_endpoints_not_found(self, no_group_client):
        token, _ = _register(no_group_client, "nogroup-user")
        headers = {"Authorization": f"Bearer {token}"}

        assert no_group_client.post("/api/v1/social/groups", headers=headers, json={"name": "x"}).status_code == 404
        assert no_group_client.post("/api/v1/social/groups/join", headers=headers, json={"invite_code": "x"}).status_code == 404
        assert no_group_client.get("/api/v1/social/groups/x").status_code == 404
        assert no_group_client.delete("/api/v1/social/groups/x", headers=headers).status_code == 404

    def test_buddy_endpoints_still_work(self, no_group_client):
        """Buddy routes should still work when groups are disabled."""
        token, _ = _register(no_group_client, "nogroup-buddy")
        headers = {"Authorization": f"Bearer {token}"}

        invite = no_group_client.post("/api/v1/social/invite", headers=headers)
        assert invite.status_code == 200
