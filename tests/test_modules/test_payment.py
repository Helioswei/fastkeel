# tests/test_modules/test_payment.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config
from fastkeel.modules import include_user, include_payment


TEST_PLANS = [
    {"id": "monthly", "name": "月度会员", "price": 1000, "duration_days": 30},
    {"id": "yearly", "name": "年度会员", "price": 9800, "duration_days": 365},
]


@pytest.fixture
def payment_app() -> FastAPI:
    config = Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret-0123456789abcdef1234",
        debug=True,
        payment_plans=TEST_PLANS,
    )
    app = create_app(config)
    include_user(app, config)
    include_payment(app, config)
    return app


@pytest.fixture
def client(payment_app):
    with TestClient(payment_app) as c:
        yield c


def _register(client, device_id="pay-test-user"):
    resp = client.post("/api/v1/auth/register", json={"device_id": device_id})
    data = resp.json()
    return data["token"], data["user"]["id"]


class TestPlans:
    """GET /api/v1/payment/plans"""

    def test_list_plans(self, client):
        resp = client.get("/api/v1/payment/plans")
        assert resp.status_code == 200
        plans = resp.json()
        assert len(plans) == 2
        plan_ids = [p["id"] for p in plans]
        assert "monthly" in plan_ids
        assert "yearly" in plan_ids

    def test_list_plans_does_not_require_auth(self, client):
        resp = client.get("/api/v1/payment/plans")
        assert resp.status_code == 200


class TestVerify:
    """POST /api/v1/payment/verify"""

    def test_verify_with_dev_provider(self, client):
        token, _ = _register(client)
        resp = client.post(
            "/api/v1/payment/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "dev",
                "receipt": {"order_id": "test-order-1", "product_id": "monthly"},
                "plan_id": "monthly",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["subscription"]["status"] == "active"
        assert "end_date" in body["subscription"]

    def test_verify_unknown_provider_returns_400(self, client):
        token, _ = _register(client)
        resp = client.post(
            "/api/v1/payment/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "nonexistent",
                "receipt": {},
                "plan_id": "monthly",
            },
        )
        assert resp.status_code == 400

    def test_verify_invalid_plan_returns_404(self, client):
        token, _ = _register(client)
        resp = client.post(
            "/api/v1/payment/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "dev",
                "receipt": {},
                "plan_id": "nonexistent",
            },
        )
        assert resp.status_code == 404

    def test_verify_requires_auth(self, client):
        resp = client.post(
            "/api/v1/payment/verify",
            json={"provider": "dev", "receipt": {}, "plan_id": "monthly"},
        )
        assert resp.status_code == 401

    def test_verify_extends_existing_subscription(self, client):
        """Verifying again with the same user extends their subscription."""
        token, _ = _register(client, "extend-user")
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "provider": "dev",
            "receipt": {"order_id": "first-order"},
            "plan_id": "monthly",
        }

        first = client.post("/api/v1/payment/verify", headers=headers, json=payload)
        first_end = first.json()["subscription"]["end_date"]

        second = client.post("/api/v1/payment/verify", headers=headers, json={
            **payload,
            "receipt": {"order_id": "second-order"},
        })
        second_end = second.json()["subscription"]["end_date"]
        assert second_end > first_end


class TestSubscription:
    """GET /api/v1/payment/subscription"""

    def test_subscription_after_verify(self, client):
        token, _ = _register(client, "sub-user")
        client.post(
            "/api/v1/payment/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "dev", "receipt": {}, "plan_id": "monthly"},
        )

        resp = client.get(
            "/api/v1/payment/subscription",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_active"] is True
        assert body["subscription"]["status"] == "active"

    def test_no_subscription(self, client):
        token, _ = _register(client, "no-sub-user")
        resp = client.get(
            "/api/v1/payment/subscription",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["has_active"] is False

    def test_subscription_requires_auth(self, client):
        resp = client.get("/api/v1/payment/subscription")
        assert resp.status_code == 401


class TestWebhook:
    """POST /api/v1/payment/webhook"""

    def test_webhook_renewal(self, client):
        token, _ = _register(client, "wh-renew")
        resp = client.post(
            "/api/v1/payment/webhook",
            headers={"X-Provider": "dev"},
            json={
                "event_type": "renewal",
                "subscription_id": "test-sub-id",
                "new_end_date": "2026-07-12T00:00:00Z",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_webhook_unknown_provider(self, client):
        resp = client.post(
            "/api/v1/payment/webhook",
            headers={"X-Provider": "unknown"},
            json={"event_type": "renewal"},
        )
        assert resp.status_code == 400

    def test_webhook_does_not_require_auth(self, client):
        resp = client.post(
            "/api/v1/payment/webhook",
            headers={"X-Provider": "dev"},
            json={"event_type": "renewal"},
        )
        assert resp.status_code == 200
