"""Authenticated API for the versioned scrap-risk model."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from ml.rebut_risk import load_artifact, predict

from ..schemas import ScrapRiskRequest, ScrapRiskResponse
from ..security import Identity, require_site, require_roles

router = APIRouter(prefix="/api/v1/scrap-risk", tags=["machine-learning"])


@lru_cache(maxsize=1)
def _model_artifact():
    path = Path(os.getenv("SCRAP_RISK_MODEL_PATH", "models/rebut_risk_v1.joblib"))
    try:
        return load_artifact(path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="scrap_risk_model_unavailable") from exc


@router.post("", response_model=ScrapRiskResponse)
def score_scrap_risk(
    payload: ScrapRiskRequest,
    identity: Identity = Depends(require_roles("viewer", "analyst", "supervisor", "admin")),
):
    require_site(identity, payload.site_id)
    frame = pd.DataFrame([payload.model_dump(exclude={"site_id"})])
    try:
        result = predict(_model_artifact(), frame).iloc[0]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="scrap_risk_feature_contract_invalid") from exc
    return {
        "model_version": str(result["model_version"]),
        "risk_probability": float(result["risk_probability"]),
        "predicted_scrap": bool(result["predicted_scrap"]),
        "threshold": float(result["threshold"]),
    }
