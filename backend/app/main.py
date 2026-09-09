"""IDDVR FastAPI application."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from .config import settings
from .db import check_connection, check_redis_connection
from .errors import unhandled_exception_handler, validation_exception_handler, http_exception_handler
from .middleware import RequestContextMiddleware
from .metrics import router as metrics_router
from .schemas import HealthResponse, ReadinessResponse
from .api.incidents import router as incidents_router
from .api.sites import router as sites_router
from .api.machines import router as machines_router
from .api.auth import router as auth_router
from .api.imports import router as imports_router
from .api.actions import router as actions_router
from .api.investigations import router as investigations_router
from .api.workspace import router as workspace_router
from .api.scrap_risk import router as scrap_risk_router
from .api.process_drift import _model_artifact, router as process_drift_router

from .api.erp_imports import router as erp_imports_router
from .api.machine_management import router as machine_management_router
from .api.machine_connections import router as machine_connections_router
from .api.shift_calendars import router as shift_calendars_router
from .api.site_management import router as site_management_router
from .api.production_planning import router as production_planning_router
from .api.site_sources import router as site_sources_router
from .api.cycle_ingestion import router as cycle_ingestion_router
from .api.hdt_control import router as hdt_control_router


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
from .api.summary6 import router as summary6_router
app.include_router(summary6_router)
app.include_router(erp_imports_router)
app.include_router(machine_management_router)
app.include_router(machine_connections_router)
app.include_router(shift_calendars_router)
app.include_router(site_management_router)
app.include_router(production_planning_router)
app.include_router(site_sources_router)
app.include_router(cycle_ingestion_router)
app.include_router(hdt_control_router)
from .api.production_context import router as production_context_router
from .api.predictions import router as predictions_router
app.include_router(production_context_router)
app.include_router(predictions_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Backward-compatible database health contract."""
    database_ok = check_connection()
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        database="ok" if database_ok else "unavailable",
    )


@app.get("/live", tags=["system"])
@app.get("/api/live", include_in_schema=False, tags=["system"])
def live() -> dict[str, str]:
    """Process liveness only; dependency failures belong to /ready."""
    return {"status": "alive"}


def check_model_artifact() -> bool:
    from ml.runtime_mode import runtime_mode
    if runtime_mode() != 'historical':
        from .services.summary6 import current
        return current()['replay_enabled']
    try:
        _model_artifact()
        return True
    except Exception:
        return False


@app.get("/ready", response_model=ReadinessResponse, tags=["system"])
@app.get("/api/ready", response_model=ReadinessResponse, include_in_schema=False, tags=["system"])
def ready():
    checks = {
        "database": check_connection(),
        "redis": check_redis_connection(),
        "model": check_model_artifact(),
    }
    available = all(checks.values())
    payload = {
        "status": "ready" if available else "not_ready",
        "service": settings.app_name,
        "version": settings.app_version,
        **{name: "ok" if value else "unavailable" for name, value in checks.items()},
    }
    if not available:
        return JSONResponse(status_code=503, content=ReadinessResponse(**payload).model_dump(mode="json"))
    return ReadinessResponse(**payload)
