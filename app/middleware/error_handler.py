"""
Global exception handlers for standardized error responses.
All errors are returned in the same envelope format as success responses.
"""
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            errors.append({
                "field": " -> ".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg"),
                "type": error.get("type"),
            })
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": errors,
                }
            }
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database error on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "An unexpected database error occurred.",
                }
            }
        )

    from app.services.auth_service import OTPRateLimitError, OTPMaxAttemptsError, InvalidOTPError
    
    @app.exception_handler(OTPRateLimitError)
    async def otp_rate_limit_handler(request: Request, exc: OTPRateLimitError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many OTP requests. Please try again later.",
                    "details": {"retry_after_seconds": exc.retry_after_seconds}
                }
            },
            headers={"Retry-After": str(exc.retry_after_seconds)}
        )

    @app.exception_handler(OTPMaxAttemptsError)
    async def otp_max_attempts_handler(request: Request, exc: OTPMaxAttemptsError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "OTP_ATTEMPTS_EXCEEDED",
                    "message": "Maximum verification attempts reached. Please request a new OTP."
                }
            }
        )

    @app.exception_handler(InvalidOTPError)
    async def invalid_otp_handler(request: Request, exc: InvalidOTPError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": "INVALID_OTP",
                    "message": "Invalid OTP code provided.",
                    "details": {"attempts_remaining": exc.attempts_remaining}
                }
            }
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred.",
                }
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # If detail is already a full error_response envelope, return it directly
        if isinstance(exc.detail, dict) and "success" in exc.detail and "error" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
            )

        # Fix: Better fallback for detail as dictionary lacking a message
        if isinstance(exc.detail, dict):
            code = exc.detail.get("code", "HTTP_ERROR")
            message = exc.detail.get("message", "An expected error occurred.")
        else:
            code = "HTTP_ERROR"
            message = str(exc.detail)
            
        # Provide meaningful defaults for standard HTTP errors if no custom code was provided
        if exc.status_code == 404 and code == "HTTP_ERROR":
            code = "NOT_FOUND"
            message = f"Resource not found: {request.url.path}"
        elif exc.status_code == 401 and code == "HTTP_ERROR":
            code = "UNAUTHORIZED"
            message = "Authentication required."
            
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                }
            }
        )
