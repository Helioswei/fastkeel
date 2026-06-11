# fastkeel/core/middleware.py
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fastkeel.core.config import Config

logger = structlog.get_logger(__name__)

# HTTP status code -> error code mapping
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
    """Register global middleware: CORS, unified error handler."""

    # CORS -- allow all origins by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global HTTPException handler
    @app.exception_handler(HTTPException)
    def custom_http_exception_handler(request: Request, exc: HTTPException):
        error_code = ERROR_MAP.get(exc.status_code, "error")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error_code, "detail": exc.detail},
        )

    # Global unhandled exception handler
    @app.exception_handler(Exception)
    def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", exc_info=exc, path=str(request.url))
        detail = str(exc) if config.debug else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": detail},
        )
