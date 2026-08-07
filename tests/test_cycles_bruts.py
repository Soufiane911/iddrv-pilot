"""Tests for the simulated raw-cycles source (scripts/generate_cycles_bruts.py).

The generated export is the connectable raw source for the HDT model: it must
match the exact column contract, stay inside plausible SI windows, be
deterministic, and run end-to-end through the HDT pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.process_drift import load_artifact, predict, prepare_inference_frame
from scripts.generate_cycles_bruts import (
    CONTRACT_COLUMNS,
    MACHINE_PROFILES,
    PLAUSIBLE_BOUNDS,
    generate_dataset,
)

ARTIFACT = ROOT / "models" / "process_drift_hdt_v1.joblib"
SEED = 42


@pytest.fixture(scope="module")
def dataset() -> pd.DataFrame:
    return generate_dataset(seed=SEED)


def test_contract_columns_exact(dataset: pd.DataFrame) -> None:
    assert list(dataset.columns) == CONTRACT_COLUMNS


def test_scrap_flag_is_binary(dataset: pd.DataFrame) -> None:
    assert set(dataset["scrap_flag"].unique()).issubset({0, 1})


def test_fleet_has_at_least_three_machines(dataset: pd.DataFrame) -> None:
    machines = dataset["machine_erp_ref"].astype(str).unique()
    assert len(machines) >= 3
    # The four documented machines are all present.
    assert set(MACHINE_PROFILES).issubset(set(machines))


def test_timestamps_increasing_with_regular_cadence(dataset: pd.DataFrame) -> None:
    for ref, group in dataset.groupby("machine_erp_ref", sort=False):
        times = pd.to_datetime(group["timestamp"], errors="coerce")
        assert times.is_monotonic_increasing, f"timestamps not sorted for {ref}"
        diffs = times.diff().dropna().dt.total_seconds()
        # Cadence is clipped to [30, 90] s; tolerance covers microsecond rounding.
        assert diffs.between(29.5, 90.5).all(), f"cadence out of [30, 90] s for {ref}"


def test_values_plausible_and_complete(dataset: pd.DataFrame) -> None:
    assert dataset[CONTRACT_COLUMNS].isna().sum().sum() == 0
    for feature, (low, high) in PLAUSIBLE_BOUNDS.items():
        values = dataset[feature]
        assert values.between(low, high).all(), (
            f"{feature} outside plausible window [{low}, {high}]"
        )


def test_generation_is_deterministic() -> None:
    first = generate_dataset(seed=SEED)
    second = generate_dataset(seed=SEED)
    pd.testing.assert_frame_equal(first, second)


def test_export_runs_through_hdt_pipeline(dataset: pd.DataFrame) -> None:
    artifact = load_artifact(ARTIFACT)
    prepared = prepare_inference_frame(dataset)
    predictions = predict(artifact, prepared)
    scores = predictions["anomaly_score"].to_numpy()
    assert np.isfinite(scores).all()
    assert bool(predictions["predicted_instability_next_20_cycles"].any())


def test_drift_episodes_are_over_detected(dataset: pd.DataFrame) -> None:
    """The HDT alert rate must be clearly higher inside drift episodes.

    Measured on seed 42: 38.5 % in the top-10 % volatility window vs 15.2 %
    on the stable bottom half (see data/cycles_bruts/README.md).
    """
    artifact = load_artifact(ARTIFACT)
    prepared = prepare_inference_frame(dataset)
    predictions = predict(artifact, prepared)
    volatility = prepared["cycle_time_s_volatility_20"].astype(float)
    alerts = predictions["predicted_instability_next_20_cycles"].to_numpy()

    mask = volatility.notna().to_numpy()
    volatility = volatility.to_numpy()[mask]
    alerts = alerts[mask]

    top = alerts[volatility >= np.quantile(volatility, 0.90)]
    bottom = alerts[volatility <= np.median(volatility)]
    assert top.mean() > bottom.mean()
