# tests/test_core/test_db.py
import fastkeel.core.db as db_mod
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.orm import Session

from fastkeel.core.config import Config
from fastkeel.core.db import Base, init_db, get_db


class DummyModel(Base):
    """Minimal model for testing table creation."""
    __tablename__ = "test_dummy"
    id = Column(String, primary_key=True)
    value = Column(Integer)


class TestInitDb:
    """Test database initialization."""

    def test_init_db_creates_engine(self):
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        assert db_mod.engine is not None
        assert db_mod.SessionLocal is not None

    def test_init_db_creates_tables(self):
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        session = db_mod.SessionLocal()
        result = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='test_dummy'")
        )
        assert result.fetchone() is not None
        session.close()

    def test_init_db_is_idempotent(self):
        """Calling init_db multiple times should not raise."""
        config = Config(db_url="sqlite:///:memory:")
        init_db(config)
        init_db(config)  # second call
        assert db_mod.engine is not None


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
        # Create the table
        Base.metadata.create_all(bind=db_mod.engine)

        gen = get_db()
        session = next(gen)
        dummy = DummyModel(id="test-1", value=42)
        session.add(dummy)
        session.commit()
        try:
            next(gen)
        except StopIteration:
            pass

        gen2 = get_db()
        session2 = next(gen2)
        loaded = session2.get(DummyModel, "test-1")
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
        session = db_mod.SessionLocal()
        result = session.execute(text("PRAGMA journal_mode"))
        row = result.fetchone()
        assert row is not None
        session.close()
