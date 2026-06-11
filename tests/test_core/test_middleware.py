# tests/test_core/test_middleware.py
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from fastkeel.core.config import Config
from fastkeel.core.middleware import register_middleware


class TestMiddleware:
    """Test middleware registration and behavior."""

    @pytest.fixture
    def app(self):
        app = FastAPI()
        config = Config(debug=True)
        register_middleware(app, config)

        @app.get("/test")
        def test_endpoint():
            return {"ok": True}

        @app.get("/error-400")
        def error_400():
            raise HTTPException(status_code=400, detail="Bad request")

        @app.get("/error-401")
        def error_401():
            raise HTTPException(status_code=401, detail="Not authenticated")

        @app.get("/error-404")
        def error_404():
            raise HTTPException(status_code=404, detail="Not found")

        @app.get("/error-409")
        def error_409():
            raise HTTPException(status_code=409, detail="Already exists")

        @app.get("/crash")
        def crash():
            raise RuntimeError("Unexpected error")

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_cors_headers(self, client):
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        # When allow_credentials=True, Starlette reflects the Origin
        # instead of using "*" (CORS spec requirement).
        assert (
            response.headers.get("access-control-allow-origin") == "http://example.com"
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_normal_response_unaffected(self, client):
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_400_formatted(self, client):
        response = client.get("/error-400")
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "bad_request"
        assert body["detail"] == "Bad request"

    def test_401_formatted(self, client):
        response = client.get("/error-401")
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "unauthorized"

    def test_404_formatted(self, client):
        response = client.get("/error-404")
        assert response.status_code == 404
        body = response.json()
        assert body["error"] == "not_found"

    def test_409_formatted(self, client):
        response = client.get("/error-409")
        assert response.status_code == 409
        body = response.json()
        assert body["error"] == "conflict"

    def test_internal_error_hides_detail_in_production(self):
        """When debug=False, hide internal error details."""
        app = FastAPI()
        config = Config(debug=False)
        register_middleware(app, config)

        @app.get("/crash")
        def crash():
            raise RuntimeError("Secret details")

        # ServerErrorMiddleware always re-raises after handling; use
        # raise_server_exceptions=False to inspect the response.
        prod_client = TestClient(app, raise_server_exceptions=False)
        response = prod_client.get("/crash")
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "internal_error"
        assert "Secret details" not in body["detail"]

    def test_internal_error_shows_detail_in_debug(self, app):
        """When debug=True, show internal error details."""
        # ServerErrorMiddleware always re-raises after handling; use
        # raise_server_exceptions=False to inspect the response.
        debug_client = TestClient(app, raise_server_exceptions=False)
        response = debug_client.get("/crash")
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "internal_error"
        assert "Unexpected error" in body["detail"]
