"""Reproducible tabular model for machine-cycle scrap risk.

The model is deliberately separate from the deterministic investigation engine:
ML estimates a risk score; the investigator remains responsible for evidence
and explanations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

MODEL_VERSION = "rebut-risk-logistic-v1"
TARGET_COLUMN = "scrap_flag"
DEFAULT_THRESHOLD = 0.5

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
NUMERIC_FEATURES = RAW_NUMERIC_FEATURES + (
    # Historical feedback is shifted by one cycle; the current label is never used.
    "previous_scrap_flag",
    "rolling_scrap_rate_20",
)
CATEGORICAL_FEATURES = ("machine_erp_ref",)
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


@dataclass(frozen=True)
class TrainingResult:
    artifact: dict[str, Any]
    metrics: dict[str, float]
    train_rows: int
    test_rows: int
    train_scraps: int
    test_scraps: int
    train_end: str
    test_start: str


def load_cycle_files(data_dir: Path) -> pd.DataFrame:
    """Load only machine-cycle CSVs from a data directory."""
    paths = sorted(data_dir.glob("machine_cycles_*.csv"))
    if not paths:
        raise FileNotFoundError(f"No machine_cycles_*.csv files found in {data_dir}")
    frames = [pd.read_csv(path) for path in paths]
    frame = pd.concat(frames, ignore_index=True)
    return prepare_frame(frame)


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate the training contract without using the current target as a feature."""
    required = set(RAW_NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) | {TARGET_COLUMN, "timestamp"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Training data is missing columns: {', '.join(missing)}")

    result = frame.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce", utc=True)
    result = result.dropna(subset=["timestamp", TARGET_COLUMN]).sort_values("timestamp")
    result[TARGET_COLUMN] = result[TARGET_COLUMN].astype(int)
    if not set(result[TARGET_COLUMN].unique()).issubset({0, 1}):
        raise ValueError(f"{TARGET_COLUMN} must contain only 0/1 values")
    result["machine_erp_ref"] = result["machine_erp_ref"].astype(str)
    # Build causal history features before restoring global chronological order.
    # At inference time these values come only from already completed cycles.
    by_machine = result.sort_values(["machine_erp_ref", "timestamp"])
    grouped_scrap = by_machine.groupby("machine_erp_ref")[TARGET_COLUMN]
    by_machine["previous_scrap_flag"] = grouped_scrap.shift(1)
    by_machine["rolling_scrap_rate_20"] = grouped_scrap.transform(
        lambda values: values.shift(1).rolling(20, min_periods=1).mean()
    )
    result = by_machine.sort_values("timestamp")
    return result.reset_index(drop=True)


def temporal_split(frame: pd.DataFrame, train_fraction: float = 2 / 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split chronologically so future cycles never train the model."""
    if not 0.5 <= train_fraction < 1:
        raise ValueError("train_fraction must be in [0.5, 1)")
    cut = max(1, min(len(frame) - 1, int(len(frame) * train_fraction)))
    train = frame.iloc[:cut].copy()
    test = frame.iloc[cut:].copy()
    if train[TARGET_COLUMN].nunique() < 2 or test[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Temporal split must contain both classes in train and test")
    return train, test


def build_pipeline() -> Pipeline:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    features = ColumnTransformer(
        transformers=[
            ("numeric", numeric, list(NUMERIC_FEATURES)),
            ("categorical", categorical, list(CATEGORICAL_FEATURES)),
        ],
        remainder="drop",
    )
    classifier = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
        solver="lbfgs",
    )
    return Pipeline([("features", features), ("classifier", classifier)])


def evaluate(model: Pipeline, test: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD) -> dict[str, float]:
    probabilities = model.predict_proba(test[list(FEATURE_COLUMNS)])[:, 1]
    actual = test[TARGET_COLUMN].to_numpy()
    predicted = (probabilities >= threshold).astype(int)
    average_precision = float(average_precision_score(actual, probabilities))
    prevalence = float(actual.mean())
    return {
        "average_precision": average_precision,
        "baseline_prevalence": prevalence,
        "lift_over_prevalence": float(average_precision / prevalence) if prevalence else 0.0,
        "roc_auc": float(roc_auc_score(actual, probabilities)),
        "precision_scrap": float(precision_score(actual, predicted, zero_division=0)),
        "recall_scrap": float(recall_score(actual, predicted, zero_division=0)),
        "threshold": float(threshold),
        "positive_predictions": float(predicted.sum()),
    }


def train(frame: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD) -> TrainingResult:
    prepared = prepare_frame(frame)
    train_frame, test_frame = temporal_split(prepared)
    model = build_pipeline()
    model.fit(train_frame[list(FEATURE_COLUMNS)], train_frame[TARGET_COLUMN])
    metrics = evaluate(model, test_frame, threshold)
    artifact: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "model": model,
        "feature_columns": list(FEATURE_COLUMNS),
        "target_column": TARGET_COLUMN,
        "threshold": threshold,
        "training_contract": {
            "split": "chronological_2_3_train_1_3_test",
            "class_weight": "balanced",
            "random_state": 42,
        },
    }
    return TrainingResult(
        artifact=artifact,
        metrics=metrics,
        train_rows=len(train_frame),
        test_rows=len(test_frame),
        train_scraps=int(train_frame[TARGET_COLUMN].sum()),
        test_scraps=int(test_frame[TARGET_COLUMN].sum()),
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
        "target_column": TARGET_COLUMN,
        "metrics": result.metrics,
        "rows": {
            "train": result.train_rows,
            "test": result.test_rows,
            "train_scraps": result.train_scraps,
            "test_scraps": result.test_scraps,
        },
        "time_boundary": {
            "train_end": result.train_end,
            "test_start": result.test_start,
        },
        "contract": result.artifact["training_contract"],
    }
    metadata_path.write_text(
        __import__("json").dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_artifact(path: Path) -> dict[str, Any]:
    artifact = joblib.load(path)
    if not isinstance(artifact, dict) or artifact.get("model_version") != MODEL_VERSION:
        raise ValueError(f"Unsupported or invalid model artifact: {path}")
    if artifact.get("feature_columns") != list(FEATURE_COLUMNS):
        raise ValueError("Model feature contract does not match runtime features")
    return artifact


def predict(artifact: dict[str, Any], frame: pd.DataFrame) -> pd.DataFrame:
    """Return a stable inference contract for one or many cycle rows."""
    missing = sorted(set(FEATURE_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"Prediction data is missing columns: {', '.join(missing)}")
    model: Pipeline = artifact["model"]
    probabilities = model.predict_proba(frame[list(FEATURE_COLUMNS)])[:, 1]
    threshold = float(artifact["threshold"])
    return pd.DataFrame(
        {
            "risk_probability": np.round(probabilities, 6),
            "predicted_scrap": probabilities >= threshold,
            "threshold": threshold,
            "model_version": artifact["model_version"],
        },
        index=frame.index,
    )
