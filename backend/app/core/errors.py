from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

class AppError(Exception):
    def __init__(self, message: str, code: str = "internal_error", status_code: int = 500, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: dict[str, Any] | None = None):
        super().__init__(message=message, code="not_found", status_code=status.HTTP_404_NOT_FOUND, details=details)

class ValidationFailed(AppError):
    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None):
        super().__init__(message=message, code="validation_error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)

class FileTooLarge(AppError):
    def __init__(self, message: str = "File exceeds maximum allowed size (10 MB)", details: dict[str, Any] | None = None):
        super().__init__(message=message, code="file_too_large", status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, details=details)

class UnsupportedFile(AppError):
    def __init__(self, message: str = "Unsupported file type. Only valid CSV files are allowed.", details: dict[str, Any] | None = None):
        super().__init__(message=message, code="unsupported_media_type", status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, details=details)

class AnalysisConflict(AppError):
    def __init__(self, message: str = "An analysis is already running for this user or dataset", details: dict[str, Any] | None = None):
        super().__init__(message=message, code="conflict", status_code=status.HTTP_409_CONFLICT, details=details)

class UnauthorizedError(AppError):
    def __init__(self, message: str = "Missing or invalid authentication credentials", details: dict[str, Any] | None = None):
        super().__init__(message=message, code="unauthorized", status_code=status.HTTP_401_UNAUTHORIZED, details=details)

class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", details: dict[str, Any] | None = None):
        super().__init__(message=message, code="forbidden", status_code=status.HTTP_403_FORBIDDEN, details=details)

class ToolArgumentError(AppError):
    """Internal validation error returned to the LLM for self-correction."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message=message, code="tool_argument_error", status_code=status.HTTP_400_BAD_REQUEST, details=details)

class LLMProviderError(AppError):
    """Internal LLM provider error to be caught by retries."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message=message, code="llm_provider_error", status_code=status.HTTP_502_BAD_GATEWAY, details=details)

# Typed errors per Part 4 specifications
class InvalidColumnError(AppError):
    def __init__(self, message: str, suggested_alternative: str | None = None, details: dict[str, Any] | None = None):
        d = details or {}
        if suggested_alternative:
            d["suggested_alternative"] = suggested_alternative
        super().__init__(message=message, code="INVALID_COLUMN", status_code=status.HTTP_400_BAD_REQUEST, details=d)

class UnsupportedChartError(AppError):
    def __init__(self, message: str, suggested_alternative: str | None = None, details: dict[str, Any] | None = None):
        d = details or {}
        if suggested_alternative:
            d["suggested_alternative"] = suggested_alternative
        super().__init__(message=message, code="UNSUPPORTED_CHART", status_code=status.HTTP_400_BAD_REQUEST, details=d)

class InsufficientDataError(AppError):
    def __init__(self, message: str, suggested_alternative: str | None = None, details: dict[str, Any] | None = None):
        d = details or {}
        if suggested_alternative:
            d["suggested_alternative"] = suggested_alternative
        super().__init__(message=message, code="INSUFFICIENT_DATA", status_code=status.HTTP_400_BAD_REQUEST, details=d)

class LimitExceededError(AppError):
    def __init__(self, message: str, suggested_alternative: str | None = None, details: dict[str, Any] | None = None):
        d = details or {}
        if suggested_alternative:
            d["suggested_alternative"] = suggested_alternative
        super().__init__(message=message, code="LIMIT_EXCEEDED", status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, details=d)

class TimeoutError(AppError):
    def __init__(self, message: str = "Operation exceeded timeout limit", suggested_alternative: str | None = None, details: dict[str, Any] | None = None):
        d = details or {}
        if suggested_alternative:
            d["suggested_alternative"] = suggested_alternative
        super().__init__(message=message, code="TIMEOUT", status_code=status.HTTP_408_REQUEST_TIMEOUT, details=d)

class CancelledError(AppError):
    def __init__(self, message: str = "Task was cancelled", suggested_alternative: str | None = None, details: dict[str, Any] | None = None):
        d = details or {}
        if suggested_alternative:
            d["suggested_alternative"] = suggested_alternative
        super().__init__(message=message, code="CANCELLED", status_code=status.HTTP_400_BAD_REQUEST, details=d)

class PrecisionWarningError(AppError):
    def __init__(self, message: str, suggested_alternative: str | None = None, details: dict[str, Any] | None = None):
        d = details or {}
        if suggested_alternative:
            d["suggested_alternative"] = suggested_alternative
        super().__init__(message=message, code="PRECISION_WARNING", status_code=status.HTTP_400_BAD_REQUEST, details=d)

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Input validation error",
                    "details": {"errors": exc.errors()}
                }
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal server error occurred",
                    "details": {"exception": str(exc)}
                }
            }
        )
