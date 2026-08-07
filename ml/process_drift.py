"""HDT: Horizon de dérive sous tolérance.

The model is an explainable, machine-contextualized anomaly detector. It learns
normal process volatility from historical non-scrap cycles and scores whether
the current multivariate trajectory is unusual. It does not replace machine
setting sheets or deterministic out-of-tolerance rules.

The current synthetic contract labels persistent instability as at least three
future scrap cycles in a 20-cycle horizon. This is an evaluation proxy only;
a production label should be replaced by a validated SPC/quality event.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_VERSION = "hdt-process-drift-iforest-v1"
TARGET_COLUMN = "instability_next_20_cycles"
SOURCE_OUTCOME_COLUMN = "scrap_flag"
HORIZON_CYCLES = 20
MIN_FUTURE_SCRAPS = 3
BASELINE_WINDOW = 20
NORMAL_SCORE_QUANTILE = 0.98

RAW_NUMERIC_FEATURES = (
    "cycle_time_s",
    "dosing_time_s",
    "injection_time_s",
    "cooling_time_s",
    "cushion_mm",
    "switchover_position_mm",
    "switchover_pressure_bar",
    "peak_pressure_bar",
    "clamp_force_kn",
    "mold_temperature_c",
    "barrel_temp_zone1_c",
    "barrel_temp_zone2_c",
    "barrel_temp_zone3_c",
    "oil_temperature_c",
    "energy_kwh",
)

DRIFT_NUMERIC_FEATURES = (
    "cycle_time_s",
    "injection_time_s",
    "cooling_time_s",
    "peak_pressure_bar",
    "clamp_force_kn",
    "mold_temperature_c",
    "barrel_temp_zone2_c",
    "energy_kwh",
)

# Volatility captures the multivariate trajectory rather than a known static
# tolerance. It is deliberately derived from current and past cycles only.
ANOMALY_FEATURES = tuple(f"{column}_volatility_20" for column in DRIFT_NUMERIC_FEATURES)
FEATURE_COLUMNS = ANOMALY_FEATURES + ("machine_erp_ref",)


@dataclass(frozen=True)
class TrainingResult:
    artifact: dict[str, Any]
    metrics: dict[str, float]
    train_rows: int
    test_rows: int
    train_events: int
    test_events: int
    train_end: str
    test_start: str


def load_cycle_files(data_dir: Path) -> pd.DataFrame:
    """Load machine cycles only; ground_truth.json is never read."""
    paths = sorted(data_dir.glob("machine_cycles_*.csv"))
    if not paths:
        raise FileNotFoundError(f"No machine_cycles_*.csv files found in {data_dir}")
    return prepare_frame(pd.concat([pd.read_csv(path) for path in paths], ignore_index=True))


def _future_event(series: pd.Series, horizon: int) -> pd.Series:
    """Build a future-only persistent-instability label."""
    future = pd.concat([series.shift(-offset) for offset in range(1, horizon + 1)], axis=1)
    valid = future.notna().all(axis=1)
    return (future.sum(axis=1) >= MIN_FUTURE_SCRAPS).where(valid).astype("float64")


def _add_volatility_features(group: pd.DataFrame) -> pd.DataFrame:
    result = group.sort_values("timestamp").copy()
    for column in DRIFT_NUMERIC_FEATURES:
        values = pd.to_numeric(result[column], errors="coerce")
        result[f"{column}_volatility_20"] = values.rolling(BASELINE_WINDOW, min_periods=3).std(ddof=0)
    return result


def _add_causal_features(group: pd.DataFrame) -> pd.DataFrame:
    result = _add_volatility_features(group)
    result[TARGET_COLUMN] = _future_event(result[SOURCE_OUTCOME_COLUMN].astype(float), HORIZON_CYCLES)
    return result


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Prepare timestamped cycles and causal volatility features."""
    required = set(RAW_NUMERIC_FEATURES) | {"timestamp", "machine_erp_ref", SOURCE_OUTCOME_COLUMN}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Training data is missing columns: {', '.join(missing)}")

    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce", utc=True)
    result = result.dropna(subset=["timestamp", SOURCE_OUTCOME_COLUMN])
    result[SOURCE_OUTCOME_COLUMN] = result[SOURCE_OUTCOME_COLUMN].astype(int)
    if not set(result[SOURCE_OUTCOME_COLUMN].unique()).issubset({0, 1}):
        raise ValueError(f"{SOURCE_OUTCOME_COLUMN} must contain only 0/1 values")
    result["machine_erp_ref"] = result["machine_erp_ref"].astype(str)
    parts = [_add_causal_features(group) for _, group in result.groupby("machine_erp_ref", sort=False)]
    result = pd.concat(parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    return result.dropna(subset=[TARGET_COLUMN]).assign(**{TARGET_COLUMN: lambda df: df[TARGET_COLUMN].astype(int)})


def prepare_inference_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Build the same causal features for runtime without a future label."""
    required = set(RAW_NUMERIC_FEATURES) | {"timestamp", "machine_erp_ref"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Inference data is missing columns: {', '.join(missing)}")
    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce", utc=True)
    result = result.dropna(subset=["timestamp"])
    result["machine_erp_ref"] = result["machine_erp_ref"].astype(str)
    parts = [_add_volatility_features(group) for _, group in result.groupby("machine_erp_ref", sort=False)]
    return pd.concat(parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def temporal_split(frame: pd.DataFrame, train_fraction: float = 2 / 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split chronologically inside each machine to avoid machine-shift leakage."""
    if not 0.5 <= train_fraction < 1:
        raise ValueError("train_fraction must be in [0.5, 1)")
    train_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    for _, group in frame.groupby("machine_erp_ref", sort=False):
        ordered = group.sort_values("timestamp").reset_index(drop=True)
        cut = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
        train_parts.append(ordered.iloc[:cut].copy())
        test_parts.append(ordered.iloc[cut:].copy())
    train = pd.concat(train_parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    test = pd.concat(test_parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    if train[TARGET_COLUMN].nunique() < 2 or test[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Per-machine temporal split must contain both instability classes")
    return train, test


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            (
                "isolation_forest",
                IsolationForest(
                    n_estimators=200,
                    contamination="auto",
                    random_state=42,
                    n_jobs=1,
                ),
            ),
        ]
    )


def _score_models(artifact: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
    scores = np.zeros(len(frame), dtype=float)
    global_model: Pipeline = artifact["global_model"]
    models: dict[str, Pipeline] = artifact["models"]
    machine_values = frame["machine_erp_ref"].astype(str).to_numpy()
    for machine in pd.unique(machine_values):
        positions = np.flatnonzero(machine_values == str(machine))
        model = models.get(str(machine), global_model)
        scores[positions] = -model.score_samples(frame.iloc[positions][list(ANOMALY_FEATURES)])
    return scores


def evaluate(artifact: dict[str, Any], test: pd.DataFrame) -> dict[str, float]:
    scores = _score_models(artifact, test)
    actual = test[TARGET_COLUMN].to_numpy()
    predicted = np.array(
        [score >= artifact["thresholds"].get(str(machine), artifact["global_threshold"])
         for score, machine in zip(scores, test["machine_erp_ref"])]
    )
    prevalence = float(actual.mean())
    average_precision = float(average_precision_score(actual, scores))
    return {
        "average_precision": average_precision,
        "baseline_prevalence": prevalence,
        "lift_over_prevalence": float(average_precision / prevalence) if prevalence else 0.0,
        "roc_auc": float(roc_auc_score(actual, scores)),
        "precision_instability": float(precision_score(actual, predicted, zero_division=0)),
        "recall_instability": float(recall_score(actual, predicted, zero_division=0)),
        "normal_score_quantile": NORMAL_SCORE_QUANTILE,
        "alert_rate": float(predicted.mean()),
        "positive_predictions": float(predicted.sum()),
        "horizon_cycles": float(HORIZON_CYCLES),
        "minimum_future_scraps": float(MIN_FUTURE_SCRAPS),
    }


def train(frame: pd.DataFrame) -> TrainingResult:
    prepared = prepare_frame(frame)
    train_frame, test_frame = temporal_split(prepared)
    normal_train = train_frame[train_frame[SOURCE_OUTCOME_COLUMN] == 0]
    global_model = build_pipeline().fit(normal_train[list(ANOMALY_FEATURES)])
    global_scores = -global_model.score_samples(normal_train[list(ANOMALY_FEATURES)])
    global_threshold = float(np.quantile(global_scores, NORMAL_SCORE_QUANTILE))

    models: dict[str, Pipeline] = {}
    thresholds: dict[str, float] = {}
    for machine, group in train_frame.groupby("machine_erp_ref", sort=False):
        normal = group[group[SOURCE_OUTCOME_COLUMN] == 0]
        model = build_pipeline().fit(normal[list(ANOMALY_FEATURES)])
        scores = -model.score_samples(normal[list(ANOMALY_FEATURES)])
        models[str(machine)] = model
        thresholds[str(machine)] = float(np.quantile(scores, NORMAL_SCORE_QUANTILE))

    artifact: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "models": models,
        "global_model": global_model,
        "feature_columns": list(FEATURE_COLUMNS),
        "anomaly_features": list(ANOMALY_FEATURES),
        "target_column": TARGET_COLUMN,
        "source_outcome_column": SOURCE_OUTCOME_COLUMN,
        "horizon_cycles": HORIZON_CYCLES,
        "minimum_future_scraps": MIN_FUTURE_SCRAPS,
        "baseline_window": BASELINE_WINDOW,
        "thresholds": thresholds,
        "global_threshold": global_threshold,
        "training_contract": {
            "target": "at_least_3_future_scraps_in_next_20_cycles_as_instability_proxy",
            "features": "causal_rolling_volatility_only",
            "normal_training_population": "historical_cycles_with_scrap_flag_0",
            "split": "chronological_2_3_train_1_3_test_per_machine",
            "algorithm": "machine_contextualized_isolation_forest",
            "ground_truth_used": False,
        },
    }
    metrics = evaluate(artifact, test_frame)
    return TrainingResult(
        artifact=artifact,
        metrics=metrics,
        train_rows=len(train_frame),
        test_rows=len(test_frame),
        train_events=int(train_frame[TARGET_COLUMN].sum()),
        test_events=int(test_frame[TARGET_COLUMN].sum()),
        train_end=train_frame["timestamp"].max().isoformat(),
        test_start=test_frame["timestamp"].min().isoformat(),
    )


def save_artifact(result: TrainingResult, artifact_path: Path, metadata_path: Path) -> None:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.artifact, artifact_path)
    metadata = {
        "model_version": MODEL_VERSION,
        "feature_columns": list(FEATURE_COLUMNS),
        "anomaly_features": list(ANOMALY_FEATURES),
        "target_column": TARGET_COLUMN,
        "source_outcome_column": SOURCE_OUTCOME_COLUMN,
        "horizon_cycles": HORIZON_CYCLES,
        "minimum_future_scraps": MIN_FUTURE_SCRAPS,
        "baseline_window": BASELINE_WINDOW,
        "metrics": result.metrics,
        "rows": {
            "train": result.train_rows,
            "test": result.test_rows,
            "train_instability_events": result.train_events,
            "test_instability_events": result.test_events,
        },
        "time_boundary": {"train_end": result.train_end, "test_start": result.test_start},
        "contract": result.artifact["training_contract"],
    }
    metadata_path.write_text(__import__("json").dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_artifact(path: Path) -> dict[str, Any]:
    artifact = joblib.load(path)
    if not isinstance(artifact, dict) or artifact.get("model_version") != MODEL_VERSION:
        raise ValueError(f"Unsupported or invalid HDT artifact: {path}")
    if artifact.get("feature_columns") != list(FEATURE_COLUMNS):
        raise ValueError("HDT model feature contract does not match runtime features")
    return artifact


def predict(artifact: dict[str, Any], frame: pd.DataFrame) -> pd.DataFrame:
    """Return anomaly score and future-instability alert for prepared cycles."""
    missing = sorted(set(FEATURE_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"Prediction data is missing columns: {', '.join(missing)}")
    scores = _score_models(artifact, frame)
    thresholds = artifact["thresholds"]
    alerts = np.array(
        [score >= thresholds.get(str(machine), artifact["global_threshold"])
         for score, machine in zip(scores, frame["machine_erp_ref"])]
    )
    return pd.DataFrame(
        {
            "anomaly_score": np.round(scores, 6),
            "predicted_instability_next_20_cycles": alerts,
            "threshold": [thresholds.get(str(machine), artifact["global_threshold"]) for machine in frame["machine_erp_ref"]],
            "horizon_cycles": artifact["horizon_cycles"],
            "model_version": artifact["model_version"],
        },
        index=frame.index,
    )
