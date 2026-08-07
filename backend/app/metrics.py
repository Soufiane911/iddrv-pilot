"""Prometheus metrics exposition with pilot-safe access control."""

from __future__ import annotations

import hmac
from typing import Callable

from fastapi import APIRouter, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter, Gauge, Histogram, generate_latest

from .config import settings

REQUEST_TOTAL = Counter(
    "iddrv_requests_total",
    "Total request count",
    ["method"],
)

HTTP_STATUS = Counter(
    "iddrv_http_status_total",
    "HTTP response status counts",
    ["status_code"],
)

REQUEST_DURATION = Histogram(
    "iddrv_request_duration_seconds",
    "Request duration in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

INVESTIGATIONS = Counter(
    "iddrv_investigations_total",
    "Investigation outcomes",
    ["outcome"],
)

DATABASE_UP = Gauge(
    "iddrv_database_up",
    "Database connection status (1 = reachable, 0 = unreachable)",
)

# HDT process-drift model monitoring (C11: score / latency / feedback).
# The anomaly score is an uncalibrated ranking score (see ml/VALIDATION-HDT.md),
# so the histogram tracks its distribution, never a probability.
PROCESS_DRIFT_PREDICTIONS = Counter(
    "iddrv_process_drift_predictions_total",
    "Successful HDT process-drift predictions",
)

PROCESS_DRIFT_SCORE = Histogram(
    "iddrv_process_drift_score",
    "HDT anomaly score distribution (uncalibrated ranking score)",
    buckets=[0.0, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 1.0, 1.5, 2.0, 5.0, 10.0],
)

PROCESS_DRIFT_ALERTS = Counter(
    "iddrv_process_drift_alerts_total",
    "HDT process-drift instability alerts raised",
)

PROCESS_DRIFT_INFERENCE_SECONDS = Histogram(
    "iddrv_process_drift_inference_seconds",
    "HDT process-drift inference latency in seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


def record_request(method: str, status_code: int, duration_s: float) -> None:
    REQUEST_TOTAL.labels(method=method).inc()
    HTTP_STATUS.labels(status_code=str(status_code)).inc()
    REQUEST_DURATION.observe(duration_s)


def set_database_up(up: bool) -> None:
    DATABASE_UP.set(1 if up else 0)


def record_investigation_outcome(outcome: str) -> None:
    valid = {"succeeded", "refused", "insufficient_data", "error"}
    if outcome not in valid:
        return
    INVESTIGATIONS.labels(outcome=outcome).inc()


def record_process_drift_prediction(score: float, alert: bool, duration_s: float) -> None:
    """Observe one successful HDT prediction: score histogram, alert counter, latency."""
    PROCESS_DRIFT_PREDICTIONS.inc()
    PROCESS_DRIFT_SCORE.observe(score)
    PROCESS_DRIFT_INFERENCE_SECONDS.observe(duration_s)
    if alert:
        PROCESS_DRIFT_ALERTS.inc()


def _provided_metrics_token(request: Request, x_metrics_token: str | None) -> str | None:
    if x_metrics_token and x_metrics_token.strip():
        return x_metrics_token.strip()
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        value = auth[7:].strip()
        return value or None
    return None


def _token_matches(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _admin_from_request(request: Request) -> bool:
    """Best-effort admin session check; invalid cookies do not unlock metrics."""
    from .security import decode_session_token, _token_from_request

    token = _token_from_request(request)
    if not token:
        return False
    identity = decode_session_token(token)
    if identity is None or identity.anonymous or not identity.is_admin:
        return False
    from .auth_repository import session_is_active

    return bool(session_is_active(identity, token))


def authorize_metrics_access(
    request: Request,
    x_metrics_token: str | None = None,
    *,
    settings_obj=None,
    admin_checker: Callable[[Request], bool] | None = None,
) -> None:
    """Allow metrics when public, scraper token matches, or caller is admin."""
    cfg = settings if settings_obj is None else settings_obj
    provided = _provided_metrics_token(request, x_metrics_token)
    expected = (cfg.metrics_token or "").strip()

    if expected:
        if provided and _token_matches(provided, expected):
            return
        checker = admin_checker or _admin_from_request
        if checker(request):
            return
        raise HTTPException(status_code=401, detail="metrics_unauthorized")

    if cfg.metrics_public:
        return

    checker = admin_checker or _admin_from_request
    if checker(request):
        return
    raise HTTPException(status_code=401, detail="metrics_unauthorized")


router = APIRouter(tags=["system"])


@router.get("/metrics")
def metrics(
    request: Request,
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
):
    authorize_metrics_access(request, x_metrics_token)
    from .db import check_connection

    set_database_up(check_connection())
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
