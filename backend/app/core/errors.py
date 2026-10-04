"""Domain exceptions and their HTTP mapping."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: dict | list | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """Raised for invalid state transitions and duplicate resources."""
    status_code = 409
    code = "conflict"


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"


class UploadError(AppError):
    status_code = 400
    code = "upload_error"


class AIProviderError(AppError):
    """The AI provider failed (network, quota, auth, timeout)."""
    status_code = 502
    code = "ai_provider_error"


class AIResponseInvalidError(AIProviderError):
    """The AI provider responded, but the output failed schema validation."""
    code = "ai_response_invalid"


def _error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details, "request_id": request_id_ctx.get()}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        log = logger.error if exc.status_code >= 500 else logger.info
        log(f"{exc.code}: {exc.message}", extra={"endpoint": request.url.path, "status_code": exc.status_code})
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err["loc"] if p != "body"), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content=_error_body("validation_error", "Request validation failed", details))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled exception", extra={"endpoint": request.url.path})
        return JSONResponse(status_code=500, content=_error_body("internal_error", "An unexpected error occurred"))
