# tests/test_core/test_auth.py
import pytest
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer

from fastkeel.core.config import Config
from fastkeel.core.auth import create_token, verify_token


class TestCreateToken:
    """Test JWT token creation."""

    def test_create_token_returns_string(self):
        config = Config(jwt_secret="test-secret")
        token = create_token("user-1", config)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_token_contains_two_dots(self):
        """JWT has three parts (header.payload.signature) separated by dots."""
        config = Config(jwt_secret="test-secret")
        token = create_token("user-1", config)
        assert token.count(".") == 2


class TestVerifyToken:
    """Test JWT token verification."""

    def test_verify_returns_user_id(self):
        config = Config(jwt_secret="test-secret")
        token = create_token("user-1", config)
        user_id = verify_token(token, config)
        assert user_id == "user-1"

    def test_verify_with_different_user_id(self):
        config = Config(jwt_secret="test-secret")
        token = create_token("user-42", config)
        user_id = verify_token(token, config)
        assert user_id == "user-42"

    def test_verify_expired_token_raises_401(self):
        """Token with negative expiration should be expired."""
        config = Config(jwt_secret="test-secret", jwt_expire_hours=-1)
        token = create_token("user-1", config)
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token, config)
        assert exc_info.value.status_code == 401

    def test_verify_invalid_token_raises_401(self):
        config = Config(jwt_secret="test-secret")
        with pytest.raises(HTTPException) as exc_info:
            verify_token("invalid.token.here", config)
        assert exc_info.value.status_code == 401

    def test_verify_wrong_secret_raises_401(self):
        config1 = Config(jwt_secret="secret-1")
        config2 = Config(jwt_secret="secret-2")
        token = create_token("user-1", config1)
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token, config2)
        assert exc_info.value.status_code == 401

    def test_empty_secret_raises_value_error(self):
        config = Config(jwt_secret="")
        with pytest.raises(ValueError, match="jwt_secret"):
            create_token("user-1", config)

    def test_missing_token_raises_401(self):
        config = Config(jwt_secret="test-secret")
        with pytest.raises(HTTPException) as exc_info:
            verify_token("", config)
        assert exc_info.value.status_code == 401


class TestOauth2Scheme:
    """Test that the OAuth2 scheme is correctly configured."""

    def test_oauth2_scheme_is_configured(self):
        from fastkeel.core.auth import oauth2_scheme
        assert isinstance(oauth2_scheme, OAuth2PasswordBearer)
