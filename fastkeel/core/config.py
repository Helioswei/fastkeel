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
    # Application
    app_name: str = "app"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    db_url: str = "sqlite:///data/app.db"
    db_echo: bool = False

    # Authentication
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 720  # 30 days

    # User module
    user_extra_fields: dict[str, type] | None = None

    # Social module
    social_enable_groups: bool = True

    # Jobs module
    jobs_config: dict[str, dict] | None = None

    # LLM
    llm_api_key: str | None = None
    llm_api_base: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_max_retries: int = 3
    llm_rate_limit: int = 10

    # Payment module
    payment_plans: list[dict] | None = None
    payment_webhook_secret: str | None = None

    @classmethod
    def from_toml(cls, path: str) -> "Config":
        """Load from TOML file, environment variables override."""
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
                # Handle nested sections: [llm] api_key -> llm_api_key
                for sub_key, sub_value in value.items():
                    full_key = f"{key}_{sub_key}"
                    if full_key in field_map:
                        kwargs[full_key] = sub_value

        config = cls(**kwargs)
        config._apply_env_overrides()
        return config

    @classmethod
    def from_env(cls) -> "Config":
        """Load only from environment variables (FASTKEEL_* prefix)."""
        config = cls()
        config._apply_env_overrides()
        return config

    def _apply_env_overrides(self) -> None:
        """Override fields from FASTKEEL_* environment variables.

        Supports both flat names (FASTKEEL_DB_URL) and nested-style names
        (FASTKEEL_LLM_API_KEY) — both resolve to the same field.
        """
        field_map = {f.name: f.type for f in fields(self)}

        for field_name, field_type in field_map.items():
            env_key = f"{ENV_PREFIX}{field_name.upper()}"
            env_value = os.environ.get(env_key)
            if env_value is not None and env_value != "":
                setattr(self, field_name, _env_to_field_value(env_value, field_type))
