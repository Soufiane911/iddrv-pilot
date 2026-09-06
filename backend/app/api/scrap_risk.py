"""Authenticated API for the versioned scrap-risk model."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from ml.artifact_contract import model_path_from_env
from ml.rebut_risk import load_artifact, predict

from ..schemas import ScrapRiskRequest, ScrapRiskResponse
from ..security import Identity, require_site, require_roles

router = APIRouter(prefix="/api/v1/scrap-risk", tags=["machine-learning"])


@lru_cache(maxsize=1)
def _model_artifact():
    path = model_path_from_env("SCRAP_RISK_MODEL_PATH", "rebut_risk_v1.joblib")
    try:
        return load_artifact(path)
    except Exception as exc:  # noqa: BLE001 - never expose pickle/contract details
        raise HTTPException(status_code=503, detail="scrap_risk_model_unavailable") from exc


@router.post("", response_model=ScrapRiskResponse)
def score_scrap_risk(
    payload: ScrapRiskRequest,
    identity: Identity = Depends(require_roles("viewer", "analyst", "supervisor", "admin")),
):
    require_site(identity, payload.site_id)
    frame = pd.DataFrame([payload.model_dump(exclude={"site_id"})])
    artifact = _model_artifact()
    try:
        result = predict(artifact, frame).iloc[0]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="scrap_risk_feature_contract_invalid") from exc
    except Exception as exc:  # noqa: BLE001 - model failures are dependency failures
        raise HTTPException(status_code=503, detail="scrap_risk_model_unavailable") from exc
    return {
        "model_version": str(result["model_version"]),
        "risk_probability": float(result["risk_probability"]),
        "predicted_scrap": bool(result["predicted_scrap"]),
        "threshold": float(result["threshold"]),
    }
