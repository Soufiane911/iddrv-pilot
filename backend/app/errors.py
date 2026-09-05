"""Common exception handlers and error envelope."""

from uuid import uuid4

from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas import ApiError


def _response(status_code: int, code: str, message: str, details: dict | None = None, request_id: str | None = None) -> JSONResponse:
    request_id = request_id or str(uuid4())
    return JSONResponse(
        status_code=status_code,
        content={"error": ApiError(code=code, message=message, details=details or {}, request_id=request_id).model_dump()},
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    return _response(422, "validation_error", "Request validation failed", {"errors": exc.errors()}, request_id=request_id)

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    code = detail if detail.endswith("_not_found") or detail.endswith("_unavailable") else "http_error"
    response = _response(exc.status_code, code, detail, request_id=request_id)
    # Preserve endpoint-specific headers such as Retry-After while ensuring
    # every error keeps the correlation header managed by the middleware.
    if exc.headers:
        for name, value in exc.headers.items():
            if name.lower() != "x-request-id":
                response.headers[name] = value
    return response


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    return _response(500, "internal_error", "Internal server error", request_id=request_id)
