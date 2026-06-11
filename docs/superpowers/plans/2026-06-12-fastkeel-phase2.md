# fastkeel Phase 2 — Social Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add social/buddy/group module to fastkeel — one-on-one buddy relationships with invite codes, and optional group management.

**Architecture:** Single `modules/social.py` file with 3 SQLAlchemy models (BuddyModel, GroupModel, GroupMemberModel), 8 API endpoints, and `include_social(app, config)`. Follows the same module pattern as `user.py`: module-level config global, `Depends(get_current_user)` for auth, and optional group routes based on `config.social_enable_groups`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2

---

## File Structure

```
fastkeel/
├── fastkeel/
│   └── modules/
│       ├── __init__.py          # MODIFIED: add include_social export
│       └── social.py            # CREATE: everything (models, routes, include_social)
├── tests/
│   ├── conftest.py              # MODIFIED: add reset_social_config
│   └── test_modules/
│       └── test_social.py       # CREATE: social module tests
```

---

### Task 1: Conftest Update

**Files:**
- Modify: `tests/conftest.py` — add social config reset

**Context:** Social module uses a module-level `_social_config` global (same pattern as user module's `_user_config`). Need to reset it between tests.

- [ ] **Step 1: Add social config reset to conftest**

In `tests/conftest.py`, add to the existing `reset_db` fixture:

```python
@pytest.fixture(autouse=True)
def reset_db():
    """Reset DB engine and module-level configs between tests."""
    import fastkeel.core.db as db_mod
    db_mod.engine = None
    db_mod.SessionLocal = None
    # Reset user module config
    import fastkeel.modules.user as user_mod
    user_mod._user_config = None
    # Social module will be imported if it exists
    try:
        import fastkeel.modules.social as social_mod
        social_mod._social_config = None
    except ImportError:
        pass
    yield
```

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "chore: add module-level config reset to test fixtures"
```

---

### Task 2: Social Module

**Files:**
- Create: `fastkeel/modules/social.py`
- Modify: `fastkeel/modules/__init__.py`
- Create: `tests/test_modules/test_social.py`

**Context:** Social module depends on user module (UserModel foreign keys). Routes use `Depends(get_current_user)` from auth.py. Group routes are optional (controlled by `config.social_enable_groups`). The module follows the same pattern as `modules/user.py`.

- [ ] **Step 1: Write the failing test**

Create `/Users/helios/AIWork/fastkeel/tests/test_modules/test_social.py`:

```python
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
        """Alice invites → Bob binds → both can see each other → Alice unbinds."""
        alice_token, alice_id = _register(client, "alice-flow")
        bob_token, bob_id = _register(client, "bob-flow")

        # Alice generates invite
        invite_resp = client.post(
            "/api/v1/social/invite",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        code = invite_resp.json()["invite_code"]

        # Bob binds
        bind_resp = client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )
        assert bind_resp.status_code == 200
        assert bind_resp.json()["status"] == "active"

        # Alice checks buddy
        alice_buddy = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert alice_buddy.status_code == 200
        assert alice_buddy.json()["buddy"]["id"] == bob_id

        # Bob checks buddy
        bob_buddy = client.get(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_buddy.status_code == 200
        assert bob_buddy.json()["buddy"]["id"] == alice_id

    def test_double_bind_returns_409(self, client):
        alice_token, _ = _register(client, "alice-double")
        bob_token, _ = _register(client, "bob-double")

        invite = client.post(
            "/api/v1/social/invite",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        code = invite.json()["invite_code"]

        # Bob binds successfully
        client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )

        # Bob tries to use same code again
        retry = client.post(
            "/api/v1/social/bind",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"invite_code": code},
        )
        assert retry.status_code == 404  # code already consumed

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

        # Bob deletes
        del_resp = client.delete(
            "/api/v1/social/buddy",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert del_resp.status_code == 200

        # Alice no longer has buddy
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
        token, _ = _register(client, "alice-group")
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
        assert body["owner_id"] == _

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

        # Group should be gone
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/helios/AIWork/fastkeel && .venv/bin/python -m pytest tests/test_modules/test_social.py -v
```
Expected: ALL FAIL (social module not found).

- [ ] **Step 3: Write the social module implementation**

Create `/Users/helios/AIWork/fastkeel/fastkeel/modules/social.py`:

```python
# fastkeel/modules/social.py
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Session

from fastkeel.core.auth import get_current_user
from fastkeel.core.config import Config
from fastkeel.core.db import Base, get_db, init_db


# ── SQLAlchemy Models ─────────────────────────────────────


class BuddyModel(Base):
    """One-on-one buddy relationship (搭子)."""
    __tablename__ = "fastkeel_buddies"

    id = Column(String, primary_key=True)
    user_a_id = Column(String, ForeignKey("fastkeel_users.id"), nullable=False)
    user_b_id = Column(String, ForeignKey("fastkeel_users.id"), nullable=True)
    invite_code = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending / active / removed
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
    role = Column(String, default="member", nullable=False)  # owner / admin / member
    joined_at = Column(DateTime, default=func.now(), nullable=False)


# ── Pydantic Schemas ──────────────────────────────────────


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
    buddy: BuddyUser | None
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


# ── Module-level config ───────────────────────────────────

_social_config: Config | None = None


def _get_config() -> Config:
    if _social_config is None:
        raise RuntimeError("Social module not initialized — call include_social() first")
    return _social_config


# ── Helpers ───────────────────────────────────────────────


def _generate_invite_code() -> str:
    """Generate a short, unique invite code."""
    return uuid.uuid4().hex[:8]


def _get_user_model():
    """Lazy import UserModel to avoid circular dependency."""
    from fastkeel.modules.user import UserModel
    return UserModel


# ── Router ────────────────────────────────────────────────

social_router = APIRouter()
group_router = APIRouter()


# ── Buddy Endpoints ───────────────────────────────────────


@social_router.post("/invite", response_model=InviteResponse)
def create_invite(
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> InviteResponse:
    """Generate a buddy invite code."""
    # Check if user already has an active buddy
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
    """Bind to a buddy using their invite code."""
    buddy = db.query(BuddyModel).filter(
        BuddyModel.invite_code == body.invite_code,
        BuddyModel.status == "pending",
        BuddyModel.user_b_id.is_(None),
    ).first()

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

    # Also create a reciprocal record so both users appear as buddies
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

    return {
        "status": buddy.status,
        "buddy_id": buddy.user_b_id,
    }


@social_router.get("/buddy", response_model=BuddyResponse)
def get_buddy(
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> BuddyResponse:
    """Get current user's buddy info."""
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
    """Remove buddy relationship."""
    buddy = _get_active_buddy(db, current_user.id)
    if buddy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No buddy relationship found",
        )

    buddy.status = "removed"

    # Also remove the reciprocal record
    if buddy.user_a_id == current_user.id:
        other_id = buddy.user_b_id
    else:
        other_id = buddy.user_a_id

    reciprocal = db.query(BuddyModel).filter(
        BuddyModel.user_a_id == other_id,
        BuddyModel.user_b_id == current_user.id,
        BuddyModel.status == "active",
    ).first()
    if reciprocal:
        reciprocal.status = "removed"

    db.commit()
    return {"status": "removed"}


def _get_active_buddy(db: Session, user_id: str) -> BuddyModel | None:
    """Find active buddy for a user. Checks both A->B and B->A records."""
    return db.query(BuddyModel).filter(
        (BuddyModel.user_a_id == user_id) | (BuddyModel.user_b_id == user_id),
        BuddyModel.status == "active",
    ).first()


# ── Group Endpoints ───────────────────────────────────────


@group_router.post("", response_model=GroupResponse)
def create_group(
    body: CreateGroupRequest,
    current_user: Any = Depends(get_current_user),
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> GroupResponse:
    """Create a new group. Creator becomes owner."""
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
    """Join a group using invite code."""
    group = db.query(GroupModel).filter(
        GroupModel.invite_code == body.invite_code,
    ).first()

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code",
        )

    # Check if already a member
    existing = db.query(GroupMemberModel).filter(
        GroupMemberModel.group_id == group.id,
        GroupMemberModel.user_id == current_user.id,
    ).first()

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
    """Get group info with members list."""
    group = db.get(GroupModel, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    members = db.query(GroupMemberModel).filter(
        GroupMemberModel.group_id == group_id,
    ).all()

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
    """Delete group. Only owner can disband."""
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

    # Delete all members
    db.query(GroupMemberModel).filter(
        GroupMemberModel.group_id == group_id,
    ).delete()

    # Delete the group
    db.delete(group)
    db.commit()
    return {"status": "deleted"}


# ── Include function ──────────────────────────────────────


def include_social(app: FastAPI, config: Config) -> None:
    """Register social module routes and models."""
    global _social_config
    _social_config = config

    init_db(config)

    # Buddy routes
    app.include_router(social_router, prefix="/api/v1/social")

    # Optional group routes
    if config.social_enable_groups:
        app.include_router(group_router, prefix="/api/v1/social/groups")
```

- [ ] **Step 4: Update modules/__init__.py**

Modify to export both `include_user` and `include_social`:

```python
from fastkeel.modules.user import include_user
from fastkeel.modules.social import include_social

__all__ = ["include_user", "include_social"]
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/helios/AIWork/fastkeel && .venv/bin/python -m pytest tests/test_modules/test_social.py -v
```
Expected: ALL PASS (23 tests).

If any fail, fix and re-run. Common issues:
- `BuddyResponse` schema: ensure `buddy` field is `BuddyUser | None` not `BuddyUser`
- `_get_active_buddy` query: check both `user_a_id` and `user_b_id` for the current user
- Reciprocal record: when user B binds, create a mirror record so both directions work

- [ ] **Step 6: Run all tests**

```bash
cd /Users/helios/AIWork/fastkeel && .venv/bin/python -m pytest -q
```
Expected: ALL PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/helios/AIWork/fastkeel && git add fastkeel/modules/social.py fastkeel/modules/__init__.py tests/test_modules/test_social.py
git commit -m "feat: add social module with buddy and group management"
```

---

### Task 3: Integration Test Update

**Files:**
- Modify: `tests/test_integration.py`

**Context:** Add social flow to integration test.

- [ ] **Step 1: Add social test to integration test**

Append to `tests/test_integration.py`:

```python
class TestSocialIntegration:
    """Social module integrated with user auth."""

    @pytest.fixture
    def full_app(self) -> FastAPI:
        config = Config(
            db_url="sqlite:///:memory:",
            jwt_secret="integration-test-secret",
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
        """Register two users → invite → bind → get buddy → remove."""
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

        # Remove
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
        """Register two users → create group → join → get → delete."""
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
```

Also update imports at top of integration test:

```python
from fastkeel.modules import include_user, include_social
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/helios/AIWork/fastkeel && .venv/bin/python -m pytest tests/test_integration.py -v
```
Expected: 6 passed (4 existing + 2 new).

```bash
cd /Users/helios/AIWork/fastkeel && .venv/bin/python -m pytest -q
```
Expected: ALL PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add social integration tests"
```
