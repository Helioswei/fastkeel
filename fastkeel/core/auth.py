# fastkeel/core/auth.py
import time
import uuid
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from fastkeel.core.config import Config
from fastkeel.core.db import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_config_dependency_instance: Config | None = None


def _get_config_dependency() -> Config:
    """FastAPI dependency returning the current Config (set during create_app)."""
    if _config_dependency_instance is None:
        raise RuntimeError("Config not set as dependency — call set_config_for_dependency()")
    return _config_dependency_instance


def set_config_for_dependency(config: Config) -> None:
    """Set the Config instance used by FastAPI dependency injection."""
    global _config_dependency_instance
    _config_dependency_instance = config


def _get_jwt_secret(config: Config) -> str:
    """Return jwt_secret or raise if empty."""
    if config.jwt_secret == "":
        raise ValueError("jwt_secret is empty — set a secret key in config")
    return config.jwt_secret


def create_token(user_id: str, config: Config) -> str:
    """签发 JWT. payload: {sub: user_id, exp, iat, jti}."""
    secret = _get_jwt_secret(config)
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + config.jwt_expire_hours * 3600,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret, algorithm=config.jwt_algorithm)


def verify_token(token: str, config: Config) -> str:
    """验证 JWT，返回 user_id。过期/无效抛出 HTTPException(401)."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    secret = _get_jwt_secret(config)
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[config.jwt_algorithm],
            options={"verify_exp": True},
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    config: Config = Depends(_get_config_dependency),
    db: Session = Depends(get_db),
) -> Any:
    """FastAPI 依赖注入：验证 token 并返回用户对象."""
    from fastkeel.modules.user import UserModel

    user_id = verify_token(token, config)
    user = db.get(UserModel, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
