"""Authenticated API for the versioned HDT process-drift model."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from ml import monitoring
from ml.hdt_registry import Catalog, load_catalog

from .. import metrics
from ..schemas import ProcessDriftRequest, ProcessDriftResponse
from ..security import Identity, require_roles, require_site

router = APIRouter(prefix="/api/v1/process-drift", tags=["machine-learning"])
LOGGER = logging.getLogger("iddrv.monitoring")


@lru_cache(maxsize=1)
def _model_artifact():
    # Service loader cache is bypassed so this historical endpoint cache retains
    # its existing environment/test invalidation behavior.
    from ..services.process_drift import model_artifact
    return model_artifact.__wrapped__()


@router.get("/candidates", response_model=Catalog)
def process_drift_candidates(
    identity: Identity = Depends(require_roles("viewer", "analyst", "supervisor", "admin")),
):
    # Global, non-site research metadata; no model loading or runtime selection.
    try:
        return load_catalog()
    except (OSError, ValueError):
        raise HTTPException(503, "hdt_catalog_unavailable") from None


@router.post("", response_model=ProcessDriftResponse)
def score_process_drift(payload: ProcessDriftRequest,
    identity: Identity = Depends(require_roles("viewer", "analyst", "supervisor", "admin"))):
    from ..services.process_drift import score_history
    require_site(identity,payload.site_id)
    from ml.runtime_mode import historical_enabled
    if not historical_enabled():
        raise HTTPException(409, 'historical_scoring_disabled: use summary6/replay; live_not_connected')
    started = time.perf_counter()
    outcome = score_history([cycle.model_dump() for cycle in payload.cycles],artifact=_model_artifact,mode='historical')
    if outcome.status != 'scored':
        raise HTTPException(503 if outcome.status == 'model_unavailable' else 422, outcome.reason)
    try:
        monitoring.record_prediction(score=outcome.score,threshold=outcome.threshold)
        metrics.record_process_drift_prediction(score=outcome.score,alert=outcome.score >= outcome.threshold,
            duration_s=time.perf_counter()-started)
    except Exception:
        LOGGER.exception("process-drift monitoring hook failed")
    return {'model_version':outcome.model_version,'machine_erp_ref':payload.cycles[0].machine_erp_ref,
        'anomaly_score':outcome.score,'predicted_instability_next_20_cycles':outcome.score >= outcome.threshold,
        'threshold':outcome.threshold,'horizon_cycles':outcome.horizon_cycles,'signals':outcome.signals}
