# tests/test_cli/test_new.py

import pytest
from typer.testing import CliRunner

from fastkeel.cli import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path):
    """Returns a tmp_path to use as output directory."""
    return tmp_path


class TestCliNew:
    """Test the `fastkeel new` command."""

    def test_new_creates_project_structure(self, runner, tmp_project):
        result = runner.invoke(app, ["new", "my-app", "--path", str(tmp_project)])
        assert result.exit_code == 0

        project_dir = tmp_project / "my-app"
        assert (project_dir / "main.py").exists()
        assert (project_dir / "config.toml").exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "project").is_dir()
        assert (project_dir / "tests").is_dir()

    def test_new_main_contains_user_import(self, runner, tmp_project):
        result = runner.invoke(app, ["new", "test-app", "--path", str(tmp_project)])
        assert result.exit_code == 0

        main_py = (tmp_project / "test-app" / "main.py").read_text()
        assert "from fastkeel.modules import include_user" in main_py
        assert "include_user(app, config)" in main_py

    def test_new_without_user_flag(self, runner, tmp_project):
        """When --with-user is False, user module should not be imported."""
        result = runner.invoke(app, ["new", "no-user", "--path", str(tmp_project), "--no-with-user"])
        assert result.exit_code == 0

        main_py = (tmp_project / "no-user" / "main.py").read_text()
        assert "include_user" not in main_py

    def test_new_with_social_flag(self, runner, tmp_project):
        result = runner.invoke(app, ["new", "social-app", "--path", str(tmp_project), "--with-social"])
        assert result.exit_code == 0

        main_py = (tmp_project / "social-app" / "main.py").read_text()
        assert "include_social" in main_py

        config = (tmp_project / "social-app" / "config.toml").read_text()
        assert "[social]" in config

    def test_new_with_payment_flag(self, runner, tmp_project):
        result = runner.invoke(app, ["new", "pay-app", "--path", str(tmp_project), "--with-payment"])
        assert result.exit_code == 0

        main_py = (tmp_project / "pay-app" / "main.py").read_text()
        assert "include_payment" in main_py

        config = (tmp_project / "pay-app" / "config.toml").read_text()
        assert "[payment]" in config

    def test_new_with_jobs_flag(self, runner, tmp_project):
        result = runner.invoke(app, ["new", "jobs-app", "--path", str(tmp_project), "--with-jobs"])
        assert result.exit_code == 0

        main_py = (tmp_project / "jobs-app" / "main.py").read_text()
        assert "include_jobs" in main_py

        config = (tmp_project / "jobs-app" / "config.toml").read_text()
        assert "[jobs]" in config

    def test_new_with_multiple_flags(self, runner, tmp_project):
        result = runner.invoke(app, [
            "new", "full-app", "--path", str(tmp_project),
            "--with-user", "--with-social", "--with-payment", "--with-jobs",
        ])
        assert result.exit_code == 0

        main_py = (tmp_project / "full-app" / "main.py").read_text()
        assert "include_user" in main_py
        assert "include_social" in main_py
        assert "include_payment" in main_py
        assert "include_jobs" in main_py

    def test_new_project_routes_template(self, runner, tmp_project):
        result = runner.invoke(app, ["new", "routes-app", "--path", str(tmp_project)])
        assert result.exit_code == 0

        routes = (tmp_project / "routes-app" / "project" / "routes" / "__init__.py").read_text()
        assert "router = APIRouter()" in routes

    def test_new_conftest_generated(self, runner, tmp_project):
        result = runner.invoke(app, ["new", "conf-app", "--path", str(tmp_project)])
        assert result.exit_code == 0

        conftest = (tmp_project / "conf-app" / "tests" / "conftest.py").read_text()
        assert "create_app" in conftest
