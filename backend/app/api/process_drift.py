"""Authenticated API for the versioned HDT process-drift model."""

from __future__ import annotations

import logging
import math
import os
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from ml import monitoring
from ml.process_drift import ANOMALY_FEATURES, HORIZON_CYCLES, RAW_NUMERIC_FEATURES, load_artifact, predict, prepare_inference_frame

from .. import metrics
from ..schemas import ProcessDriftRequest, ProcessDriftResponse
from ..security import Identity, require_roles, require_site

router = APIRouter(prefix="/api/v1/process-drift", tags=["machine-learning"])
LOGGER = logging.getLogger("iddrv.monitoring")


@lru_cache(maxsize=1)
def _model_artifact():
    """Load the HDT artifact only when the first valid request needs it."""
    path = Path(os.getenv("PROCESS_DRIFT_MODEL_PATH", "models/process_drift_hdt_v1.joblib"))
    try:
        artifact = load_artifact(path)
        required_keys = {"models", "global_model", "thresholds", "global_threshold", "horizon_cycles"}
        if not required_keys.issubset(artifact):
            raise ValueError("HDT artifact is missing its runtime contract")
        if artifact["horizon_cycles"] != HORIZON_CYCLES:
            raise ValueError("HDT artifact horizon does not match the runtime contract")
        if not isinstance(artifact["models"], dict) or not isinstance(artifact["thresholds"], dict):
            raise ValueError("HDT artifact model registry is invalid")
        thresholds = [artifact["global_threshold"], *artifact["thresholds"].values()]
        if any(not math.isfinite(float(value)) for value in thresholds):
            raise ValueError("HDT artifact thresholds are invalid")
        return artifact
    except Exception as exc:
        # Loading/unpickling errors are deliberately not exposed to API clients.
        raise HTTPException(status_code=503, detail="process_drift_model_unavailable") from exc


def _signals(prepared: pd.DataFrame) -> list[dict[str, float | str]]:
    """Return only observed, highest causal volatilities; no causal claim is made."""
    latest = prepared.iloc[-1]
    available: list[tuple[str, float]] = []
    for feature in ANOMALY_FEATURES:
        value = latest.get(feature)
        if value is None or pd.isna(value):
            continue
        numeric_value = float(value)
        if math.isfinite(numeric_value):
            available.append((feature, numeric_value))
    available.sort(key=lambda item: (-item[1], item[0]))
    return [{"feature": feature, "volatility": value} for feature, value in available[:3]]


@router.post("", response_model=ProcessDriftResponse)
def score_process_drift(
    payload: ProcessDriftRequest,
    identity: Identity = Depends(require_roles("viewer", "analyst", "supervisor", "admin")),
):
    require_site(identity, payload.site_id)

    frame = pd.DataFrame([cycle.model_dump() for cycle in payload.cycles])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    if frame["timestamp"].isna().any():
        raise HTTPException(status_code=422, detail="process_drift_timestamps_invalid")
    if frame["machine_erp_ref"].nunique() != 1:
        raise HTTPException(status_code=422, detail="process_drift_multiple_machines")
    if not frame[list(RAW_NUMERIC_FEATURES)].notna().any(axis=None):
        raise HTTPException(status_code=422, detail="process_drift_raw_features_missing")

    # The model prepares causal history itself. Sorting here makes the latest
    # cycle unambiguous even when the client sends the history out of order.
    frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    try:
        prepared = prepare_inference_frame(frame)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="process_drift_feature_contract_invalid") from exc
    if prepared.empty:
        raise HTTPException(status_code=422, detail="process_drift_history_empty")

    artifact = _model_artifact()
    started = time.perf_counter()
    try:
        result = predict(artifact, prepared.iloc[[-1]]).iloc[0]
    except Exception as exc:
        # A broken artifact must not become an opaque 500 response.
        raise HTTPException(status_code=503, detail="process_drift_model_unavailable") from exc
    inference_seconds = time.perf_counter() - started

    # Monitoring (score distribution, alert rate, Prometheus) is a side channel:
    # it must never change the response contract or fail the request.
    try:
        anomaly_score = float(result["anomaly_score"])
        alert = bool(result["predicted_instability_next_20_cycles"])
        monitoring.record_prediction(score=anomaly_score, threshold=float(result["threshold"]))
        metrics.record_process_drift_prediction(score=anomaly_score, alert=alert, duration_s=inference_seconds)
    except Exception:  # noqa: BLE001
        LOGGER.exception("process-drift monitoring hook failed")

    return {
        "model_version": str(result["model_version"]),
        "machine_erp_ref": str(prepared.iloc[-1]["machine_erp_ref"]),
        "anomaly_score": float(result["anomaly_score"]),
        "predicted_instability_next_20_cycles": bool(result["predicted_instability_next_20_cycles"]),
        "threshold": float(result["threshold"]),
        "horizon_cycles": int(result["horizon_cycles"]),
        "signals": _signals(prepared),
    }
