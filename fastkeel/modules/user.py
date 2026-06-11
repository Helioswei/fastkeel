# fastkeel/modules/user.py
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.orm import Session

from fastkeel.core.auth import create_token, get_current_user
from fastkeel.core.config import Config
from fastkeel.core.db import Base, get_db, init_db


class UserModel(Base):
    """Device-registered user model."""
    __tablename__ = "fastkeel_users"

    id = Column(String, primary_key=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    nickname = Column(String, default="", nullable=False)
    avatar_url = Column(String, default="", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class RegisterRequest(BaseModel):
    device_id: str


class LoginRequest(BaseModel):
    device_id: str


class UpdateMeRequest(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None


class UserResponse(BaseModel):
    id: str
    device_id: str
    nickname: str
    avatar_url: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


_user_config: Config | None = None


def _get_config() -> Config:
    if _user_config is None:
        raise RuntimeError("User module not initialized — call include_user() first")
    return _user_config


user_router = APIRouter()


@user_router.post("/register", response_model=AuthResponse)
def register(
    body: RegisterRequest,
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Device registration -> returns JWT. If device_id exists, returns existing user + new token."""
    existing = db.query(UserModel).filter(UserModel.device_id == body.device_id).first()
    if existing:
        token = create_token(existing.id, config)
        return AuthResponse(token=token, user=UserResponse.model_validate(existing))

    user = UserModel(
        id=uuid.uuid4().hex,
        device_id=body.device_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id, config)
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@user_router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Device login -> refresh JWT. Unregistered device_id returns 404."""
    user = db.query(UserModel).filter(UserModel.device_id == body.device_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not registered",
        )
    token = create_token(user.id, config)
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@user_router.get("/me", response_model=UserResponse)
def get_me(
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    """Get current user info."""
    return UserResponse.model_validate(current_user)


@user_router.patch("/me", response_model=UserResponse)
def update_me(
    body: UpdateMeRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update nickname/avatar."""
    if body.nickname is not None:
        current_user.nickname = body.nickname
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


def include_user(app: FastAPI, config: Config) -> None:
    """Register user module routes and models."""
    global _user_config
    _user_config = config

    # Ensure DB is initialized and tables created
    init_db(config)

    # Register routes
    app.include_router(user_router, prefix="/api/v1/auth")
