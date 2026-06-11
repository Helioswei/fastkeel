# fastkeel/modules/social.py
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Session

from fastkeel.core.auth import get_current_user
from fastkeel.core.config import Config
from fastkeel.core.db import Base, get_db, init_db


class BuddyModel(Base):
    """One-on-one buddy relationship (搭子)."""

    __tablename__ = "fastkeel_buddies"

    id = Column(String, primary_key=True)
    user_a_id = Column(String, ForeignKey("fastkeel_users.id"), nullable=False)
    user_b_id = Column(String, ForeignKey("fastkeel_users.id"), nullable=True)
    invite_code = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class GroupModel(Base):
    """Group."""

    __tablename__ = "fastkeel_groups"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("fastkeel_users.id"), nullable=False)
    invite_code = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class GroupMemberModel(Base):
    """Group membership."""

    __tablename__ = "fastkeel_group_members"

    group_id = Column(String, ForeignKey("fastkeel_groups.id"), primary_key=True)
    user_id = Column(String, ForeignKey("fastkeel_users.id"), primary_key=True)
    role = Column(String, default="member", nullable=False)
    joined_at = Column(DateTime, default=func.now(), nullable=False)


class InviteResponse(BaseModel):
    invite_code: str


class BindRequest(BaseModel):
    invite_code: str


class BuddyUser(BaseModel):
    id: str
    nickname: str
    avatar_url: str

    model_config = {"from_attributes": True}


class BuddyResponse(BaseModel):
    buddy: BuddyUser | None = None
    status: str | None = None


class CreateGroupRequest(BaseModel):
    name: str


class JoinGroupRequest(BaseModel):
    invite_code: str


class GroupMemberResponse(BaseModel):
    user_id: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    invite_code: str
    members: list[GroupMemberResponse] = []

    model_config = {"from_attributes": True}


_social_config: Config | None = None


def _get_config() -> Config:
    if _social_config is None:
        raise RuntimeError("Social module not initialized -- call include_social() first")
    return _social_config


def _generate_invite_code() -> str:
    return uuid.uuid4().hex[:8]


def _get_user_model():
    from fastkeel.modules.user import UserModel

    return UserModel


social_router = APIRouter()
group_router = APIRouter()


@social_router.post("/invite", response_model=InviteResponse)
def create_invite(
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> InviteResponse:
    existing = _get_active_buddy(db, current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already has a buddy",
        )

    buddy = BuddyModel(
        id=uuid.uuid4().hex,
        user_a_id=current_user.id,
        invite_code=_generate_invite_code(),
    )
    db.add(buddy)
    db.commit()
    return InviteResponse(invite_code=buddy.invite_code)


@social_router.post("/bind")
def bind_buddy(
    body: BindRequest,
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> dict:
    buddy = (
        db.query(BuddyModel)
        .filter(
            BuddyModel.invite_code == body.invite_code,
            BuddyModel.status == "pending",
            BuddyModel.user_b_id.is_(None),
        )
        .first()
    )

    if buddy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite code",
        )

    if buddy.user_a_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot bind to your own invite code",
        )

    buddy.user_b_id = current_user.id
    buddy.status = "active"

    reciprocal = BuddyModel(
        id=uuid.uuid4().hex,
        user_a_id=current_user.id,
        user_b_id=buddy.user_a_id,
        invite_code=_generate_invite_code(),
        status="active",
    )
    db.add(reciprocal)
    db.commit()
    db.refresh(buddy)

    return {"status": buddy.status, "buddy_id": buddy.user_b_id}


@social_router.get("/buddy", response_model=BuddyResponse)
def get_buddy(
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> BuddyResponse:
    buddy_record = _get_active_buddy(db, current_user.id)
    if buddy_record is None:
        return BuddyResponse(buddy=None)

    buddy_user_id = (
        buddy_record.user_b_id
        if buddy_record.user_a_id == current_user.id
        else buddy_record.user_a_id
    )

    UserModel = _get_user_model()
    buddy_user = db.get(UserModel, buddy_user_id)
    if buddy_user is None:
        return BuddyResponse(buddy=None)

    return BuddyResponse(
        buddy=BuddyUser(
            id=buddy_user.id,
            nickname=buddy_user.nickname,
            avatar_url=buddy_user.avatar_url,
        ),
        status=buddy_record.status,
    )


@social_router.delete("/buddy")
def remove_buddy(
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> dict:
    buddy = _get_active_buddy(db, current_user.id)
    if buddy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No buddy relationship found",
        )

    buddy.status = "removed"

    if buddy.user_a_id == current_user.id:
        other_id = buddy.user_b_id
    else:
        other_id = buddy.user_a_id

    # Find the reciprocal record in either direction
    reciprocal = (
        db.query(BuddyModel)
        .filter(
            (
                (BuddyModel.user_a_id == other_id)
                & (BuddyModel.user_b_id == current_user.id)
            )
            | (
                (BuddyModel.user_a_id == current_user.id)
                & (BuddyModel.user_b_id == other_id)
            ),
            BuddyModel.status == "active",
            BuddyModel.id != buddy.id,
        )
        .first()
    )
    if reciprocal:
        reciprocal.status = "removed"

    db.commit()
    return {"status": "removed"}


def _get_active_buddy(db: Session, user_id: str) -> BuddyModel | None:
    return (
        db.query(BuddyModel)
        .filter(
            (BuddyModel.user_a_id == user_id) | (BuddyModel.user_b_id == user_id),
            BuddyModel.status == "active",
        )
        .first()
    )


@group_router.post("", response_model=GroupResponse)
def create_group(
    body: CreateGroupRequest,
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> GroupResponse:
    group = GroupModel(
        id=uuid.uuid4().hex,
        name=body.name,
        owner_id=current_user.id,
        invite_code=_generate_invite_code(),
    )
    db.add(group)
    db.flush()

    member = GroupMemberModel(
        group_id=group.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(member)
    db.commit()

    return GroupResponse(
        id=group.id,
        name=group.name,
        owner_id=group.owner_id,
        invite_code=group.invite_code,
        members=[GroupMemberResponse.model_validate(member)],
    )


@group_router.post("/join", response_model=GroupMemberResponse)
def join_group(
    body: JoinGroupRequest,
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> GroupMemberResponse:
    group = (
        db.query(GroupModel)
        .filter(
            GroupModel.invite_code == body.invite_code,
        )
        .first()
    )

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code",
        )

    existing = (
        db.query(GroupMemberModel)
        .filter(
            GroupMemberModel.group_id == group.id,
            GroupMemberModel.user_id == current_user.id,
        )
        .first()
    )

    if existing:
        return GroupMemberResponse.model_validate(existing)

    member = GroupMemberModel(
        group_id=group.id,
        user_id=current_user.id,
        role="member",
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return GroupMemberResponse.model_validate(member)


@group_router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: str,
    db: Session = Depends(get_db),
) -> GroupResponse:
    group = db.get(GroupModel, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    members = (
        db.query(GroupMemberModel)
        .filter(
            GroupMemberModel.group_id == group_id,
        )
        .all()
    )

    return GroupResponse(
        id=group.id,
        name=group.name,
        owner_id=group.owner_id,
        invite_code=group.invite_code,
        members=[GroupMemberResponse.model_validate(m) for m in members],
    )


@group_router.delete("/{group_id}")
def delete_group(
    group_id: str,
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    group = db.get(GroupModel, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    if group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can delete the group",
        )

    db.query(GroupMemberModel).filter(
        GroupMemberModel.group_id == group_id,
    ).delete()

    db.delete(group)
    db.commit()
    return {"status": "deleted"}


def include_social(app: FastAPI, config: Config) -> None:
    """Register social module routes and models."""
    global _social_config
    _social_config = config

    init_db(config)

    app.include_router(social_router, prefix="/api/v1/social")

    if config.social_enable_groups:
        app.include_router(group_router, prefix="/api/v1/social/groups")
