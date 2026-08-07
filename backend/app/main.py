"""IDDVR FastAPI application."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from .config import settings
from .db import check_connection
from .errors import unhandled_exception_handler, validation_exception_handler, http_exception_handler
from .middleware import RequestContextMiddleware
from .metrics import router as metrics_router
from .schemas import HealthResponse
from .api.incidents import router as incidents_router
from .api.sites import router as sites_router
from .api.machines import router as machines_router
from .api.auth import router as auth_router
from .api.imports import router as imports_router
from .api.actions import router as actions_router
from .api.investigations import router as investigations_router
from .api.workspace import router as workspace_router
from .api.scrap_risk import router as scrap_risk_router
from .api.process_drift import router as process_drift_router


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(RequestContextMiddleware)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(metrics_router)
app.include_router(incidents_router)
app.include_router(sites_router)
app.include_router(machines_router)
app.include_router(auth_router)
app.include_router(imports_router)
app.include_router(actions_router)
app.include_router(investigations_router)
app.include_router(workspace_router)
app.include_router(scrap_risk_router)
app.include_router(process_drift_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    database_ok = check_connection()
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        database="ok" if database_ok else "unavailable",
    )
