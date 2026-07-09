"""IDDVR FastAPI application skeleton (G1)."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .config import settings
from .db import check_connection
from .errors import unhandled_exception_handler, validation_exception_handler
from .schemas import HealthResponse


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    database_ok = check_connection()
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        database="ok" if database_ok else "unavailable",
    )
