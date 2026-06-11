# tests/test_modules/test_jobs.py
import pytest
from fastapi import FastAPI

from fastkeel import create_app, Config
from fastkeel.modules import include_jobs


@pytest.fixture(autouse=True)
def cleanup_scheduler():
    """Ensure scheduler is stopped after each test."""
    yield
    import fastkeel.modules.jobs as jobs_mod
    if jobs_mod.scheduler and jobs_mod.scheduler.running:
        jobs_mod.scheduler.shutdown(wait=False)
    jobs_mod.scheduler = None


@pytest.fixture
def jobs_config():
    return {
        "test_interval_job": {"trigger": "interval", "seconds": 10},
    }


@pytest.fixture
def app_with_jobs(jobs_config) -> FastAPI:
    config = Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret-0123456789abcdef1234",
        debug=True,
        jobs_config=jobs_config,
    )
    app = create_app(config)
    include_jobs(app, config)
    return app


class TestJobs:
    """Test APScheduler integration."""

    def test_scheduler_created_and_running(self, app_with_jobs):
        from fastkeel.modules.jobs import scheduler
        assert scheduler is not None
        assert scheduler.running is True

    def test_heartbeat_job_registered(self, app_with_jobs):
        from fastkeel.modules.jobs import scheduler
        job = scheduler.get_job("_fastkeel_heartbeat")
        assert job is not None
        assert job.id == "_fastkeel_heartbeat"

    def test_custom_job_registered(self, app_with_jobs):
        from fastkeel.modules.jobs import scheduler
        job = scheduler.get_job("test_interval_job")
        assert job is not None

    def test_no_jobs_config_creates_only_heartbeat(self):
        config = Config(
            db_url="sqlite:///:memory:",
            jwt_secret="test-secret-0123456789abcdef1234",
            jobs_config=None,
        )
        app = create_app(config)
        include_jobs(app, config)

        from fastkeel.modules.jobs import scheduler
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "_fastkeel_heartbeat"

    def test_resolve_job_func_fallback(self):
        """Unknown job name should fall back to no-op without crashing."""
        from fastkeel.modules.jobs import resolve_job_func
        func = resolve_job_func("nonexistent_job")
        assert callable(func)
        result = func()
        assert result is None
