"""One HDT calculation contract for historical requests and durable observations."""
from dataclasses import dataclass, field
from functools import lru_cache
import math
import pandas as pd
from ml.artifact_contract import model_path_from_env
from ml.process_drift import (ANOMALY_FEATURES, DRIFT_NUMERIC_FEATURES, RAW_NUMERIC_FEATURES,
    HORIZON_CYCLES, load_artifact, predict, prepare_inference_frame)

@dataclass(frozen=True)
class ScoringOutcome:
    status: str
    reason: str | None = None
    model_version: str | None = None
    model_scope: str | None = None
    score: float | None = None
    threshold: float | None = None
    signals: list = field(default_factory=list)
    horizon_cycles: int = HORIZON_CYCLES
    input_count: int = 0

@lru_cache(maxsize=1)
def model_artifact():
    """Load the HDT artifact only when the first valid request needs it."""
    path = model_path_from_env("PROCESS_DRIFT_MODEL_PATH", "process_drift_hdt_v1.joblib")
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
        raise RuntimeError("process_drift_model_unavailable") from exc


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



def score_history(cycles: list[dict], *, artifact, mode: str) -> ScoringOutcome:
    if mode not in {'live','backfill','historical'}:
        raise ValueError('scoring_mode_invalid')
    count = len(cycles)
    def abstain(status, reason):
        return ScoringOutcome(status, reason, input_count=count)
    if count < (3 if mode == 'historical' else 20):
        return abstain('insufficient_history', 'twenty_cycles_required' if mode != 'historical' else 'three_cycles_required')
    frame = pd.DataFrame(cycles)
    if 'timestamp' not in frame or 'machine_erp_ref' not in frame:
        return abstain('incompatible', 'process_drift_feature_contract_invalid')
    frame['timestamp'] = pd.to_datetime(frame['timestamp'],errors='coerce',utc=True)
    if frame['timestamp'].isna().any():
        return abstain('incompatible','process_drift_timestamps_invalid')
    if frame['machine_erp_ref'].nunique() != 1:
        return abstain('incompatible','process_drift_multiple_machines')
    frame = frame.sort_values('timestamp',kind='stable').reset_index(drop=True)
    if mode != 'historical':
        frame = frame.iloc[-20:]
        for cycle in sorted(cycles,key=lambda row: pd.Timestamp(row['timestamp']))[-20:]:
            units = cycle.get('units', {})
            if not isinstance(units,dict):
                return abstain('incompatible','units_contract_invalid')
            for feature in DRIFT_NUMERIC_FEATURES:
                unit = feature.rsplit('_',1)[-1]
                if feature in units and units[feature] != unit:
                    return abstain('incompatible','incompatible_units:' + feature)
        for feature in DRIFT_NUMERIC_FEATURES:
            if feature not in frame:
                return abstain('incompatible','missing_feature:' + feature)
            try:
                if not all(value is not None and not isinstance(value,bool) and math.isfinite(float(value)) for value in frame[feature]):
                    return abstain('incompatible','non_finite_or_missing_feature:' + feature)
            except (TypeError,ValueError):
                return abstain('incompatible','non_numeric_feature:' + feature)
    if not frame.reindex(columns=RAW_NUMERIC_FEATURES).notna().any(axis=None):
        return abstain('incompatible','process_drift_raw_features_missing')
    try:
        prepared = prepare_inference_frame(frame)
    except (TypeError,ValueError):
        return abstain('incompatible','process_drift_feature_contract_invalid')
    if prepared.empty:
        return abstain('incompatible','process_drift_history_empty')
    try:
        loaded = artifact() if callable(artifact) else artifact
        result = predict(loaded,prepared.iloc[[-1]]).iloc[0]
        score,threshold = float(result['anomaly_score']),float(result['threshold'])
        if not math.isfinite(score) or not math.isfinite(threshold):
            raise ValueError('non_finite_prediction')
    except Exception:
        return abstain('model_unavailable','process_drift_model_unavailable')
    machine = str(prepared.iloc[-1]['machine_erp_ref'])
    scope = 'machine' if machine in loaded['models'] else 'global'
    return ScoringOutcome('scored', 'global_model_requires_qualification' if scope == 'global' else None,
        str(result['model_version']),scope,score,threshold,_signals(prepared),int(result['horizon_cycles']),count)
