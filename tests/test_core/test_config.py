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
        config = Config(jwt_secret="my-secret-0123456789abcdefghijkl")
        assert config.jwt_secret == "my-secret-0123456789abcdefghijkl"

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
