"""Common exception handlers and error envelope."""

from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas import ApiError


def _response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    request_id = str(uuid4())
    return JSONResponse(
        status_code=status_code,
        content={"error": ApiError(code=code, message=message, details=details or {}, request_id=request_id).model_dump()},
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _response(422, "validation_error", "Request validation failed", {"errors": exc.errors()})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(500, "internal_error", "Internal server error")
