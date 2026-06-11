# fastkeel/core/app.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastkeel.core.auth import set_config_for_dependency
from fastkeel.core.config import Config
from fastkeel.core.middleware import register_middleware


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: startup / shutdown."""
    # Startup: DB init is deferred to first include_*() call
    yield
    # Shutdown: nothing to clean up (SQLite handles itself)


def create_app(config: Config) -> FastAPI:
    """Create a FastAPI app instance. Register middleware, lifecycle hooks."""
    app = FastAPI(title=config.app_name, debug=config.debug, lifespan=_lifespan)

    # Store config for access elsewhere
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
