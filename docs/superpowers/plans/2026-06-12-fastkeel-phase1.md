# fastkeel Phase 1 — Core + User Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the fastkeel PyPI package MVP — `core/` infrastructure (config, db, auth, middleware, app factory) + `user` module (device registration, login, JWT auth).

**Architecture:** Layered composition — `core/` provides foundational services (Config → DB → Auth → Middleware → App factory). `modules/user.py` registers routes and models on top of core. All synchronous FastAPI + SQLAlchemy.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (sync), PyJWT, structlog, pytest

**Key Design Decisions (see CLAUDE.md for details):**
- Sync SQLAlchemy + `def` routes (no async)
- `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` for Swagger auth
- Error responses: `{"error": "code", "detail": "msg", "code?": "optional"}`
- DB init on first `include_*()` call, not during `create_app()`
- CLI flags only for modules, not contrib

---

## File Structure

```
fastkeel/
├── pyproject.toml
├── fastkeel/
│   ├── __init__.py                    # Exports: create_app, Config
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                  # Config dataclass, TOML + env loading
│   │   ├── db.py                      # init_db, get_db, Base
│   │   ├── auth.py                    # create_token, verify_token, get_current_user
│   │   ├── middleware.py              # register_middleware (CORS, error handler)
│   │   └── app.py                     # create_app factory
│   └── modules/
│       ├── __init__.py                # include_user
│       └── user.py                    # UserModel + auth routes
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_core/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_db.py
│   │   ├── test_auth.py
│   │   ├── test_middleware.py
│   │   └── test_app.py
│   └── test_modules/
│       ├── __init__.py
│       └── test_user.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `fastkeel/pyproject.toml`
- Create: `fastkeel/__init__.py`
- Create: `fastkeel/core/__init__.py`
- Create: `fastkeel/modules/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_core/__init__.py`
- Create: `tests/test_modules/__init__.py`

**Context:** This is the foundation for the entire package. All subsequent tasks depend on these files existing.

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "fastkeel"
version = "0.1.0"
description = "FastAPI backend scaffold — user auth, social, subscriptions, jobs & LLM"
authors = [{ name = "Helioswei" }]
license = { text = "MIT" }
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.100.0,<1.0.0",
    "sqlalchemy>=2.0.0,<3.0.0",
    "pyjwt>=2.0.0,<3.0.0",
    "apscheduler>=3.10.0,<4.0.0",
    "httpx>=0.25.0,<1.0.0",
    "jinja2>=3.0.0,<4.0.0",
    "typer>=0.9.0,<1.0.0",
    "structlog>=23.0.0,<25.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0,<9.0.0",
    "ruff>=0.1.0,<1.0.0",
    "build>=1.0.0,<2.0.0",
    "twine>=4.0.0,<6.0.0",
]

[project.urls]
Homepage = "https://github.com/helioswei/fastkeel"

[project.scripts]
fastkeel = "fastkeel.cli:app"
```

- [ ] **Step 2: Create fastkeel/__init__.py**

```python
from fastkeel.core.app import create_app
from fastkeel.core.config import Config

__all__ = ["create_app", "Config"]
```

- [ ] **Step 3: Create fastkeel/core/__init__.py** (empty)

- [ ] **Step 4: Create fastkeel/modules/__init__.py**

```python
from fastkeel.modules.user import include_user

__all__ = ["include_user"]
```

- [ ] **Step 5: Create three empty `__init__.py` files**

```
tests/__init__.py
tests/test_core/__init__.py
tests/test_modules/__init__.py
```

- [ ] **Step 6: Verify structure and install**

```bash
cd /Users/helios/AIWork/fastkeel
pip install -e ".[dev]"
```

Expected: `pip install` succeeds, `python -c "import fastkeel; print('ok')"` prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold fastkeel package structure"
```

---

### Task 2: Config Module

**Files:**
- Create: `fastkeel/core/config.py`
- Create: `tests/test_core/test_config.py`

**Context:** `config.py` is the type-safe configuration root. Every other module depends on it. It supports construction via constructor, TOML file loading (with env var overrides), and pure env-var loading. All subsequent tasks will import `Config` from this path.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core/test_config.py
import pytest
from fastkeel.core.config import Config


class TestConfigDefaults:
    """Test that Config has correct default values."""

    def test_default_app_name(self):
        config = Config()
        assert config.app_name == "app"

    def test_default_db_url(self):
        config = Config()
        assert config.db_url == "sqlite:///data/app.db"

    def test_default_jwt_secret_is_empty(self):
        config = Config()
        assert config.jwt_secret == ""

    def test_default_jwt_algorithm(self):
        config = Config()
        assert config.jwt_algorithm == "HS256"

    def test_default_jwt_expire(self):
        config = Config()
        assert config.jwt_expire_hours == 720

    def test_debug_default_false(self):
        config = Config()
        assert config.debug is False


class TestConfigCustomization:
    """Test that Config accepts constructor overrides."""

    def test_custom_app_name(self):
        config = Config(app_name="my-app")
        assert config.app_name == "my-app"

    def test_custom_db_url(self):
        config = Config(db_url="sqlite:///:memory:")
        assert config.db_url == "sqlite:///:memory:"

    def test_custom_jwt_secret(self):
        config = Config(jwt_secret="my-secret")
        assert config.jwt_secret == "my-secret"

    def test_extra_fields_default_none(self):
        config = Config()
        assert config.user_extra_fields is None

    def test_extra_fields_custom(self):
        config = Config(user_extra_fields={"score": int})
        assert config.user_extra_fields == {"score": int}


class TestConfigFromToml:
    """Test loading Config from TOML file."""

    def test_from_toml_basic(self, tmp_path):
        toml_content = """
app_name = "test-app"
db_url = "sqlite:///test.db"
jwt_secret = "toml-secret"
"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(toml_content)

        config = Config.from_toml(str(config_path))
        assert config.app_name == "test-app"
        assert config.db_url == "sqlite:///test.db"
        assert config.jwt_secret == "toml-secret"

    def test_from_toml_partial_override(self, tmp_path):
        """Only override specified fields, keep defaults for others."""
        toml_content = 'app_name = "minimal"'
        config_path = tmp_path / "config.toml"
        config_path.write_text(toml_content)

        config = Config.from_toml(str(config_path))
        assert config.app_name == "minimal"
        assert config.db_url == "sqlite:///data/app.db"  # default

    def test_from_toml_nested_sections(self, tmp_path):
        """Handle TOML section keys like [user] extra_fields."""
        toml_content = """
[user]
extra_fields = { detox_score = "integer" }

[llm]
api_key = "sk-test"
"""
        config_path = tmp_path / "config.toml"
        config_path.write_text(toml_content)

        config = Config.from_toml(str(config_path))
        assert config.llm_api_key == "sk-test"

    def test_from_toml_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            Config.from_toml("/nonexistent/config.toml")


class TestConfigFromEnv:
    """Test loading Config from environment variables."""

    def test_from_env_basic(self, monkeypatch):
        monkeypatch.setenv("FASTKEEL_APP_NAME", "env-app")
        monkeypatch.setenv("FASTKEEL_DB_URL", "sqlite:///env.db")
        monkeypatch.setenv("FASTKEEL_JWT_SECRET", "env-secret")

        config = Config.from_env()
        assert config.app_name == "env-app"
        assert config.db_url == "sqlite:///env.db"
        assert config.jwt_secret == "env-secret"

    def test_from_env_defaults_remain(self, monkeypatch):
        """Only override fields that have env vars set."""
        monkeypatch.setenv("FASTKEEL_JWT_SECRET", "s")
        config = Config.from_env()
        assert config.app_name == "app"  # default

    def test_from_env_empty_secret_does_not_override_default(self, monkeypatch):
        monkeypatch.setenv("FASTKEEL_JWT_SECRET", "")
        config = Config.from_env()
        assert config.jwt_secret == ""


class TestConfigIntegration:
    """Test that from_toml with env override works correctly."""

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        """Environment variables should override TOML values."""
        toml_content = 'app_name = "toml-app"'
        config_path = tmp_path / "config.toml"
        config_path.write_text(toml_content)

        monkeypatch.setenv("FASTKEEL_APP_NAME", "env-app")
        config = Config.from_toml(str(config_path))
        assert config.app_name == "env-app"

    def test_toml_without_env_keeps_toml_value(self, tmp_path):
        """Without env set, TOML value is used."""
        toml_content = 'app_name = "toml-app"'
        config_path = tmp_path / "config.toml"
        config_path.write_text(toml_content)

        config = Config.from_toml(str(config_path))
        assert config.app_name == "toml-app"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_config.py -v
```

Expected: ALL FAIL — `Config` class not found.

- [ ] **Step 3: Write Config implementation**

```python
# fastkeel/core/config.py
import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Union


ENV_PREFIX = "FASTKEEL_"


def _env_to_field_value(env_value: str, field_type: type) -> Any:
    """Convert env var string to appropriate Python type."""
    if field_type is bool:
        return env_value.lower() in ("true", "1", "yes")
    if field_type is int:
        return int(env_value)
    if field_type is float:
        return float(env_value)
    if field_type is str:
        return env_value
    # Handle Optional types (Union[X, None])
    origin = getattr(field_type, "__origin__", None)
    if origin is Union:
        args = field_type.__args__
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _env_to_field_value(env_value, non_none[0])
    return env_value


@dataclass
class Config:
    # 应用
    app_name: str = "app"
    debug: bool = False

    # 服务
    host: str = "0.0.0.0"
    port: int = 8000

    # 数据库
    db_url: str = "sqlite:///data/app.db"
    db_echo: bool = False

    # 认证
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 720  # 30 天

    # 用户模块
    user_extra_fields: dict[str, type] | None = None

    # 社交模块
    social_enable_groups: bool = True

    # 任务模块
    jobs_config: dict[str, dict] | None = None

    # LLM
    llm_api_key: str | None = None
    llm_api_base: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_max_retries: int = 3
    llm_rate_limit: int = 10

    # 支付模块
    payment_plans: list[dict] | None = None
    payment_webhook_secret: str | None = None

    @classmethod
    def from_toml(cls, path: str) -> "Config":
        """从 TOML 文件加载，环境变量覆盖."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path_obj.open("rb") as f:
            data = tomllib.load(f)

        # Build kwargs: flat keys map directly, nested sections use underscore
        kwargs: dict[str, Any] = {}
        field_map = {f.name: f.type for f in fields(cls)}

        for key, value in data.items():
            if key in field_map:
                kwargs[key] = value
            elif isinstance(value, dict):
                # Handle nested sections: [llm] api_key → llm_api_key
                for sub_key, sub_value in value.items():
                    full_key = f"{key}_{sub_key}"
                    if full_key in field_map:
                        kwargs[full_key] = sub_value

        config = cls(**kwargs)
        config._apply_env_overrides()
        return config

    @classmethod
    def from_env(cls) -> "Config":
        """仅从环境变量加载（FASTKEEL_* 前缀）."""
        config = cls()
        config._apply_env_overrides()
        return config

    def _apply_env_overrides(self) -> None:
        """Override fields from FASTKEEL_* environment variables."""
        field_map = {f.name: f.type for f in fields(self)}

        for field_name, field_type in field_map.items():
            env_key = f"{ENV_PREFIX}{field_name.upper()}"
            env_value = os.environ.get(env_key)
            if env_value is not None and env_value != "":
                setattr(self, field_name, _env_to_field_value(env_value, field_type))

        # Also handle nested-style env vars (e.g. FASTKEEL_LLM_API_KEY)
        for field_name, field_type in field_map.items():
            if "_" in field_name:
                parts = field_name.split("_", 1)
                env_key = f"{ENV_PREFIX}{parts[0].upper()}_{parts[1].upper()}"
                env_value = os.environ.get(env_key)
                if env_value is not None and env_value != "":
                    setattr(self, field_name, _env_to_field_value(env_value, field_type))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_config.py -v
```

Expected: ALL PASS. If any fail, fix Config implementation and re-run.

- [ ] **Step 5: Commit**

```bash
git add fastkeel/core/config.py tests/test_core/test_config.py
git commit -m "feat: add Config dataclass with TOML + env var loading"
```

---

### Task 3: DB Module

**Files:**
- Create: `fastkeel/core/db.py`
- Create: `tests/test_core/test_db.py`

**Context:** DB module manages SQLAlchemy engine, session lifecycle, and the declarative `Base` that all models inherit from. It uses a module-level global singleton pattern (`engine`, `SessionLocal`) with `init_db()` being idempotent — safe to call multiple times. Uses synchronous SQLite with WAL mode. All subsequent tasks that need database access depend on this module.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core/test_db.py
import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session

from fastkeel.core.config import Config
from fastkeel.core.db import Base, init_db, get_db, engine, SessionLocal


class TestDummyModel(Base):
    """Minimal model for testing table creation."""
    __tablename__ = "test_dummy"
    id = Column(String, primary_key=True)
    value = Column(Integer)


class TestInitDb:
    """Test database initialization."""

    def test_init_db_creates_engine(self):
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        assert engine is not None
        assert SessionLocal is not None

    def test_init_db_creates_tables(self):
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        session = SessionLocal()
        result = session.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_dummy'"
        )
        assert result.fetchone() is not None
        session.close()

    def test_init_db_is_idempotent(self):
        """Calling init_db multiple times should not raise."""
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        init_db(config)  # second call
        assert engine is not None


class TestGetDb:
    """Test database session lifecycle."""

    def test_get_db_returns_session(self):
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        gen = get_db()
        session = next(gen)
        assert isinstance(session, Session)
        try:
            next(gen)
        except StopIteration:
            pass

    def test_get_db_session_can_write_and_read(self):
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        Base.metadata.create_all(bind=engine)

        gen = get_db()
        session = next(gen)
        dummy = TestDummyModel(id="test-1", value=42)
        session.add(dummy)
        session.commit()
        try:
            next(gen)
        except StopIteration:
            pass

        # Read back in a new session
        gen2 = get_db()
        session2 = next(gen2)
        loaded = session2.get(TestDummyModel, "test-1")
        assert loaded is not None
        assert loaded.value == 42
        try:
            next(gen2)
        except StopIteration:
            pass


class TestSqlitePragmas:
    """Test that SQLite WAL mode pragma doesn't crash."""

    def test_wal_pragma_does_not_crash(self):
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        session = SessionLocal()
        result = session.execute("PRAGMA journal_mode")
        row = result.fetchone()
        assert row is not None
        session.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_db.py -v
```

Expected: ALL FAIL — imports from db.py not found.

- [ ] **Step 3: Write DB implementation**

```python
# fastkeel/core/db.py
import sqlite3
from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from fastkeel.core.config import Config

engine: Engine | None = None
SessionLocal: sessionmaker | None = None
Base = declarative_base()


def init_db(config: Config) -> None:
    """Initialize SQLAlchemy engine and session factory.

    Idempotent — safe to call multiple times.
    Enables SQLite WAL mode when using sqlite:// URL.
    Creates all registered tables via Base.metadata.create_all().
    """
    global engine, SessionLocal

    if engine is not None:
        return  # already initialized

    connect_args: dict[str, Any] = {}
    if config.db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        config.db_url,
        echo=config.db_echo,
        connect_args=connect_args,
    )

    # Enable WAL mode for SQLite
    if config.db_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create all registered tables
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a DB session, auto-close on request end."""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db(config) first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_db.py -v
```

Expected: ALL PASS. If `test_init_db_creates_tables` fails, check that `TestDummyModel` module-level definition is visible to `Base.metadata` before `init_db()` is called.

- [ ] **Step 5: Commit**

```bash
git add fastkeel/core/db.py tests/test_core/test_db.py
git commit -m "feat: add DB module with SQLAlchemy init, WAL mode, session management"
```

---

### Task 4: Auth Module

**Files:**
- Create: `fastkeel/core/auth.py`
- Create: `tests/test_core/test_auth.py`

**Context:** Auth module provides JWT creation (`create_token`), verification (`verify_token`), and a FastAPI dependency (`get_current_user`) for protected routes. Uses `OAuth2PasswordBearer` for Swagger compatibility. Token creation requires `Config.jwt_secret` to be non-empty. Auth routes in `modules/user.py` will depend on this module.

- [ ] **Step 1: Write the failing test**

```python
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
        assert len(token) > 20  # JWT should be reasonably long

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
        with pytest.raises(ValueError, match="jwt_secret is empty"):
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
        assert oauth2_scheme.model_config.get("tokenUrl") == "/api/v1/auth/login"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_auth.py -v
```

Expected: ALL FAIL — imports from auth.py not found.

- [ ] **Step 3: Write Auth implementation**

```python
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

# Sentinel used by get_current_user via FastAPI Depends
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
    if not config.jwt_secret:
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
        return payload["sub"]
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
    """FastAPI 依赖注入：验证 token 并返回用户对象。

    Import UserModel lazily to avoid circular import at module level.
    UserModel must be registered (via include_user) before first request.
    """
    from fastkeel.modules.user import UserModel

    user_id = verify_token(token, config)
    user = db.get(UserModel, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_auth.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add fastkeel/core/auth.py tests/test_core/test_auth.py
git commit -m "feat: add JWT auth module with create/verify token, OAuth2 scheme"
```

---

### Task 5: Middleware Module

**Files:**
- Create: `fastkeel/core/middleware.py`
- Create: `tests/test_core/test_middleware.py`

**Context:** Middleware module registers global CORS, structured logging, and a unified error handler that converts all `HTTPException`s and unhandled exceptions into the standard `{"error": "...", "detail": "..."}` format. Uses `structlog` for logging. The `register_middleware(app, config)` function is called by `create_app`.

- [ ] **Step 1: Write the failing test**

```python
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
        assert response.headers.get("access-control-allow-origin") == "*"

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

        prod_client = TestClient(app)
        response = prod_client.get("/crash")
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "internal_error"
        assert "Secret details" not in body["detail"]

    def test_internal_error_shows_detail_in_debug(self, client):
        """When debug=True, show internal error details."""
        response = client.get("/crash")
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "internal_error"
        assert "Unexpected error" in body["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_middleware.py -v
```

Expected: ALL FAIL — `register_middleware` not found.

- [ ] **Step 3: Write Middleware implementation**

```python
# fastkeel/core/middleware.py
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fastkeel.core.config import Config

logger = structlog.get_logger(__name__)

# HTTP 状态码 → error code 映射
ERROR_MAP: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}


def register_middleware(app: FastAPI, config: Config) -> None:
    """注册全局中间件: CORS, 统一错误处理."""

    # CORS — 默认允许所有来源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局 HTTPException 处理器
    @app.exception_handler(HTTPException)
    def custom_http_exception_handler(request: Request, exc: HTTPException):
        error_code = ERROR_MAP.get(exc.status_code, "error")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error_code, "detail": exc.detail},
        )

    # 全局未预期异常处理器
    @app.exception_handler(Exception)
    def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", exc_info=exc, path=str(request.url))
        detail = str(exc) if config.debug else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": detail},
        )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_middleware.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add fastkeel/core/middleware.py tests/test_core/test_middleware.py
git commit -m "feat: add middleware module with CORS, error handler"
```

---

### Task 6: App Factory

**Files:**
- Create: `fastkeel/core/app.py`
- Create: `tests/test_core/test_app.py`

**Context:** App factory ties together middleware, config, and lifespan management. `create_app(config)` returns a configured FastAPI instance with health check endpoint. DB initialization is NOT done here — it's deferred to the first `include_*()` call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core/test_app.py
import pytest
from fastapi import FastAPI

from fastkeel.core.config import Config
from fastkeel.core.app import create_app


class TestCreateApp:
    """Test the FastAPI app factory."""

    def test_create_app_returns_fastapi_instance(self):
        config = Config(db_url="sqlite:///:memory:", jwt_secret="test-secret")
        app = create_app(config)
        assert isinstance(app, FastAPI)

    def test_app_has_correct_title(self):
        config = Config(
            app_name="test-app",
            db_url="sqlite:///:memory:",
            jwt_secret="test-secret",
        )
        app = create_app(config)
        assert app.title == "test-app"

    def test_root_health_check(self):
        from fastapi.testclient import TestClient

        config = Config(
            app_name="test-app",
            db_url="sqlite:///:memory:",
            jwt_secret="test-secret",
        )
        app = create_app(config)
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["app"] == "test-app"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_app.py -v
```

Expected: ALL FAIL — `create_app` not found.

- [ ] **Step 3: Write App Factory implementation**

```python
# fastkeel/core/app.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastkeel.core.auth import set_config_for_dependency
from fastkeel.core.config import Config
from fastkeel.core.middleware import register_middleware


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期: startup / shutdown."""
    # Startup: DB init is deferred to first include_*() call
    yield
    # Shutdown: nothing to clean up (SQLite handles itself)


def create_app(config: Config) -> FastAPI:
    """创建 FastAPI 应用实例. 注册中间件、挂载生命周期钩子."""
    app = FastAPI(title=config.app_name, debug=config.debug, lifespan=_lifespan)

    # Store config for access in lifespan and routes
    app.state.config = config

    # Set config for auth dependency injection
    set_config_for_dependency(config)

    # Register middleware (CORS, error handling)
    register_middleware(app, config)

    # Health check
    @app.get("/")
    def health_check():
        return {"status": "ok", "app": config.app_name}

    return app
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_core/test_app.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add fastkeel/core/app.py tests/test_core/test_app.py
git commit -m "feat: add app factory with lifespan, health check, middleware"
```

---

### Task 7: Test Conftest

**Files:**
- Modify: `tests/conftest.py`

**Context:** Shared test fixtures used by module-level tests. The `reset_db` fixture is essential — it clears the DB global singleton between tests so each test gets a fresh in-memory database.

- [ ] **Step 1: Write conftest.py**

```python
# tests/conftest.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config


@pytest.fixture(autouse=True)
def reset_db():
    """Reset DB engine between tests so each test gets a fresh in-memory database."""
    import fastkeel.core.db as db_mod
    db_mod.engine = None
    db_mod.SessionLocal = None
    yield


@pytest.fixture
def raw_config() -> Config:
    """Base test config with in-memory SQLite."""
    return Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret",
        debug=True,
    )


@pytest.fixture
def app(raw_config: Config) -> FastAPI:
    """Create a minimal FastAPI app without any modules."""
    return create_app(raw_config)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 2: Verify conftest loads correctly**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/ --co -q
```

Expected: No errors (the `--co` flag collects tests only, no actual tests to run since test files exist but no test functions in conftest). If `--co` is not supported, just run `python -c "import conftest"` from the tests dir.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "chore: add test fixtures (config, app, client, reset_db)"
```

---

### Task 8: User Module

**Files:**
- Create: `fastkeel/modules/user.py`
- Create: `tests/test_modules/test_user.py`

**Context:** User module provides device-based authentication. The `UserModel` is a SQLAlchemy model registered on `Base`. Four API endpoints: register (POST → returns JWT + user), login (POST → refresh JWT), get me (GET → user info), update me (PATCH → change nickname/avatar). `include_user(app, config)` ties it all together by calling `init_db(config)` and registering the router.

- [ ] **Step 1: Write the failing test**

```python
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
        # Token should be different (new JWT)
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
        body = response.json()
        assert body["error"] == "unauthorized"

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_modules/test_user.py -v
```

Expected: ALL FAIL — imports from `modules/user.py` not found.

- [ ] **Step 3: Write User Module implementation**

```python
# fastkeel/modules/user.py
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.orm import Session

from fastkeel.core.auth import create_token, get_current_user, verify_token
from fastkeel.core.config import Config
from fastkeel.core.db import Base, get_db, init_db

# ── SQLAlchemy Model ──────────────────────────────────────


class UserModel(Base):
    """设备注册用户模型。"""
    __tablename__ = "fastkeel_users"

    id = Column(String, primary_key=True)  # UUID
    device_id = Column(String, unique=True, index=True, nullable=False)
    nickname = Column(String, default="", nullable=False)
    avatar_url = Column(String, default="", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # 扩展字段通过 config.user_extra_fields 动态添加（Phase 2）


# ── Pydantic Schemas ──────────────────────────────────────


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


# ── Module-level config for FastAPI Depends ───────────────

_user_config: Config | None = None


def _get_config() -> Config:
    if _user_config is None:
        raise RuntimeError("User module not initialized — call include_user() first")
    return _user_config


# ── Router ────────────────────────────────────────────────

user_router = APIRouter()


@user_router.post("/register", response_model=AuthResponse)
def register(
    body: RegisterRequest,
    config: Config = Depends(_get_config),
    db: Session = Depends(get_db),
) -> AuthResponse:
    """设备注册 → 返回 JWT。如果 device_id 已存在则返回已有用户 + 新 token。"""
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
    """设备登录 → 刷新 JWT。未注册的 device_id 返回 404。"""
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
    """获取当前用户信息。"""
    return UserResponse.model_validate(current_user)


@user_router.patch("/me", response_model=UserResponse)
def update_me(
    body: UpdateMeRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """更新昵称/头像。"""
    if body.nickname is not None:
        current_user.nickname = body.nickname
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ── Include function ─────────────────────────────────────


def include_user(app: FastAPI, config: Config) -> None:
    """注册 user 模块的所有路由和模型。"""
    global _user_config
    _user_config = config

    # 确保 DB 已初始化并创建表
    init_db(config)

    # 注册路由
    app.include_router(user_router, prefix="/api/v1/auth")
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_modules/test_user.py -v
```

Expected: ALL PASS.

If test failures occur due to the `reset_db` fixture not clearing things properly, check ordering: `reset_db` is autouse=True so it runs before each test function. The `user_app` fixture creates a new app + include_user + init_db after the reset. The `user_client` fixture creates a new TestClient for each test. If issues persist, add `scope="function"` explicitly to the `user_app` fixture.

- [ ] **Step 5: Commit**

```bash
git add fastkeel/modules/user.py tests/test_modules/test_user.py
git commit -m "feat: add user module with register, login, me, update routes"
```

---

### Task 9: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Context:** An integration test that verifies the full user auth flow works end-to-end: register → use token → get me → update → login again → verify new token.

- [ ] **Step 1: Write the integration test**

```python
# tests/test_integration.py
"""End-to-end integration tests for the full user auth flow."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkeel import create_app, Config
from fastkeel.modules import include_user


@pytest.fixture
def full_app() -> FastAPI:
    config = Config(
        db_url="sqlite:///:memory:",
        jwt_secret="integration-test-secret",
        debug=True,
    )
    app = create_app(config)
    include_user(app, config)
    return app


@pytest.fixture
def client(full_app: FastAPI) -> TestClient:
    with TestClient(full_app) as c:
        yield c


class TestFullAuthFlow:
    """Complete auth lifecycle: register → me → update → login → me again."""

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
        """Register → update → login again → verify updated fields."""
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
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/helios/AIWork/fastkeel
pytest tests/test_integration.py -v
```

Expected: ALL PASS.

- [ ] **Step 3: Run all tests**

```bash
cd /Users/helios/AIWork/fastkeel
pytest -v
```

Expected: ALL PASS (config + db + auth + middleware + app + user + integration).

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test for auth flow"
```

---
