#!/usr/bin/env python3
"""Generate a realistic simulated raw-cycle export for the IDDRV HDT model.

This script produces an industrial-style raw cycles export (EUROMAP/Arburg-like
CSV files) for a small fleet of injection-molding machines. The generated data
is SYNTHETIC: it mimics the shape of a factory export (stable per-machine
regime, plausible sensor noise, slow drift episodes, scrap bursts) but is not
real plant data.

Design principles:
- Deterministic: a single ``numpy.random.default_rng(seed)`` drives every draw,
  so the same seed always produces byte-identical CSV files.
- Machine profiles are calibrated on the HDT training data
  (``data/scenarios/industrial_demo/machine_cycles_*.csv``): setpoints and
  sensor noise match the normal regime of each known machine, and drift
  episodes are sized so that the rolling volatility they create is large
  enough to exceed the HDT per-machine thresholds (98th percentile of normal
  scores) — proving the raw source is connectable to the existing pipeline.
- Machines 152, 1003 and 606 are already known to the HDT artifact (per-machine
  IsolationForest). Machine 870 is new: it exercises the global-model fallback.

Usage:
    env -u PYTHONPATH .venv/bin/python scripts/generate_cycles_bruts.py --seed 42
    env -u PYTHONPATH .venv/bin/python scripts/generate_cycles_bruts.py --seed 42 --score
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.process_drift import RAW_NUMERIC_FEATURES, load_artifact, predict, prepare_inference_frame

# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

# Exact column contract of a raw cycles export: timestamp, machine ERP ref,
# the 15 HDT raw numeric features, and the scrap flag (0/1). This is the single
# source of truth used by both the generator and the tests.
CONTRACT_COLUMNS: list[str] = [
    "timestamp",
    "machine_erp_ref",
    *list(RAW_NUMERIC_FEATURES),
    "scrap_flag",
]

# Global plausibility windows (SI units) used to clip generated values. Wide
# enough to cover every machine profile, tight enough to reject sensor garbage.
PLAUSIBLE_BOUNDS: dict[str, tuple[float, float]] = {
    "cycle_time_s": (10.0, 120.0),
    "dosing_time_s": (1.0, 30.0),
    "injection_time_s": (0.5, 20.0),
    "cooling_time_s": (3.0, 60.0),
    "cushion_mm": (1.0, 15.0),
    "switchover_position_mm": (5.0, 40.0),
    "switchover_pressure_bar": (20.0, 400.0),
    "peak_pressure_bar": (20.0, 2500.0),
    "clamp_force_kn": (100.0, 6000.0),
    "mold_temperature_c": (20.0, 150.0),
    "barrel_temp_zone1_c": (40.0, 300.0),
    "barrel_temp_zone2_c": (40.0, 300.0),
    "barrel_temp_zone3_c": (40.0, 300.0),
    "oil_temperature_c": (20.0, 100.0),
    "energy_kwh": (0.05, 10.0),
}

# Export window: a ~30 h production window, naive local timestamps (like the
# historical training export), microseconds precision.
EXPORT_START = pd.Timestamp("2026-07-27 06:00:00")
EXPORT_STAGGER_HOURS = {"152": 0.0, "1003": 2.5, "606": 5.0, "870": 8.0}

DEFAULT_SEED = 42
DEFAULT_CYCLES_PER_MACHINE = 2500
DEFAULT_OUTPUT_DIR = Path("data/cycles_bruts")
DEFAULT_ARTIFACT = Path("models/process_drift_hdt_v1.joblib")

# Features that may carry a drift episode (subset of the HDT drift features
# observed by the model). Others stay on their stable regime.
DRIFT_DRIVERS = (
    "cycle_time_s",
    "injection_time_s",
    "cooling_time_s",
    "peak_pressure_bar",
    "clamp_force_kn",
    "mold_temperature_c",
    "barrel_temp_zone2_c",
    "energy_kwh",
)

# Cadence spec: a cycle every 30-90 s per machine.
MIN_CADENCE_S = 30.0
MAX_CADENCE_S = 90.0

# Scrap budget: bursts inside instability episodes + rare isolated scraps.
SCRAP_ISOLATED_PROB = 0.006
SCRAP_BURST_MIN = 6
SCRAP_BURST_MAX = 20


# ---------------------------------------------------------------------------
# Machine profiles
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureProfile:
    """Stable-regime setpoint, sensor noise and normal volatility reference."""

    mean: float
    noise: float
    # ``drift_std`` is the 98th percentile of the rolling-20 volatility of
    # normal cycles (measured on the HDT training data). Drift episodes are
    # sized as a multiple of it so the model actually reacts.
    drift_std: float = 0.0


@dataclass(frozen=True)
class MachineProfile:
    """A machine: ERP ref, human label, cycle cadence and feature regimes."""

    ref: str
    label: str
    cadence_base_s: float
    features: dict[str, FeatureProfile]


MACHINE_PROFILES: dict[str, MachineProfile] = {
    # Engel victory 160 — small technical part, fast cycle.
    "152": MachineProfile(
        ref="152",
        label="Engel victory 160",
        cadence_base_s=38.0,
        features={
            "cycle_time_s": FeatureProfile(21.2, 0.50, drift_std=1.01),
            "dosing_time_s": FeatureProfile(4.0, 0.15),
            "injection_time_s": FeatureProfile(2.0, 0.30, drift_std=0.37),
            "cooling_time_s": FeatureProfile(11.5, 2.00, drift_std=2.41),
            "cushion_mm": FeatureProfile(4.8, 0.25),
            "switchover_position_mm": FeatureProfile(16.5, 0.50),
            "switchover_pressure_bar": FeatureProfile(210.0, 6.0),
            "peak_pressure_bar": FeatureProfile(750.0, 29.0, drift_std=36.5),
            "clamp_force_kn": FeatureProfile(600.0, 30.0, drift_std=36.8),
            "mold_temperature_c": FeatureProfile(45.0, 2.80, drift_std=3.46),
            "barrel_temp_zone1_c": FeatureProfile(198.0, 1.20),
            "barrel_temp_zone2_c": FeatureProfile(210.0, 2.90, drift_std=3.52),
            "barrel_temp_zone3_c": FeatureProfile(205.0, 1.20),
            "oil_temperature_c": FeatureProfile(48.0, 0.60),
            "energy_kwh": FeatureProfile(0.40, 0.06, drift_std=0.074),
        },
    ),
    # Arburg Allrounder 520A — medium part, well instrumented.
    "1003": MachineProfile(
        ref="1003",
        label="Arburg Allrounder 520A",
        cadence_base_s=52.0,
        features={
            "cycle_time_s": FeatureProfile(31.5, 0.50, drift_std=1.53),
            "dosing_time_s": FeatureProfile(6.0, 0.20),
            "injection_time_s": FeatureProfile(3.0, 0.57, drift_std=0.71),
            "cooling_time_s": FeatureProfile(16.0, 2.30, drift_std=2.71),
            "cushion_mm": FeatureProfile(5.2, 0.30),
            "switchover_position_mm": FeatureProfile(18.5, 0.60),
            "switchover_pressure_bar": FeatureProfile(195.0, 6.0),
            "peak_pressure_bar": FeatureProfile(851.0, 29.0, drift_std=35.9),
            "clamp_force_kn": FeatureProfile(1350.0, 85.0, drift_std=103.2),
            "mold_temperature_c": FeatureProfile(57.5, 4.20, drift_std=5.13),
            "barrel_temp_zone1_c": FeatureProfile(215.0, 1.20),
            "barrel_temp_zone2_c": FeatureProfile(227.5, 4.20, drift_std=5.21),
            "barrel_temp_zone3_c": FeatureProfile(220.0, 1.20),
            "oil_temperature_c": FeatureProfile(52.0, 0.70),
            "energy_kwh": FeatureProfile(1.00, 0.11, drift_std=0.139),
        },
    ),
    # Two-platen press — large part, high clamp force.
    "606": MachineProfile(
        ref="606",
        label="Presse deux plateaux 450 t",
        cadence_base_s=66.0,
        features={
            "cycle_time_s": FeatureProfile(41.7, 0.50, drift_std=1.64),
            "dosing_time_s": FeatureProfile(7.5, 0.25),
            "injection_time_s": FeatureProfile(4.5, 0.85, drift_std=1.03),
            "cooling_time_s": FeatureProfile(23.0, 2.80, drift_std=3.50),
            "cushion_mm": FeatureProfile(6.0, 0.30),
            "switchover_position_mm": FeatureProfile(21.0, 0.70),
            "switchover_pressure_bar": FeatureProfile(220.0, 7.0),
            "peak_pressure_bar": FeatureProfile(976.0, 43.0, drift_std=52.2),
            "clamp_force_kn": FeatureProfile(3000.0, 280.0, drift_std=341.9),
            "mold_temperature_c": FeatureProfile(65.0, 5.60, drift_std=6.82),
            "barrel_temp_zone1_c": FeatureProfile(228.0, 1.30),
            "barrel_temp_zone2_c": FeatureProfile(242.5, 4.20, drift_std=5.18),
            "barrel_temp_zone3_c": FeatureProfile(233.0, 1.30),
            "oil_temperature_c": FeatureProfile(55.0, 0.80),
            "energy_kwh": FeatureProfile(2.01, 0.28, drift_std=0.345),
        },
    ),
    # New machine (not seen during HDT training) -> global-model fallback.
    "870": MachineProfile(
        ref="870",
        label="Machine neuve 280 t (non connue du HDT)",
        cadence_base_s=61.0,
        features={
            "cycle_time_s": FeatureProfile(38.0, 0.55, drift_std=1.50),
            "dosing_time_s": FeatureProfile(6.8, 0.22),
            "injection_time_s": FeatureProfile(3.4, 0.50, drift_std=0.70),
            "cooling_time_s": FeatureProfile(18.5, 2.40, drift_std=2.80),
            "cushion_mm": FeatureProfile(5.6, 0.30),
            "switchover_position_mm": FeatureProfile(19.5, 0.60),
            "switchover_pressure_bar": FeatureProfile(205.0, 6.0),
            "peak_pressure_bar": FeatureProfile(920.0, 30.0, drift_std=36.0),
            "clamp_force_kn": FeatureProfile(2200.0, 70.0, drift_std=100.0),
            "mold_temperature_c": FeatureProfile(60.0, 4.00, drift_std=5.10),
            "barrel_temp_zone1_c": FeatureProfile(210.0, 1.20),
            "barrel_temp_zone2_c": FeatureProfile(235.0, 4.00, drift_std=5.20),
            "barrel_temp_zone3_c": FeatureProfile(225.0, 1.20),
            "oil_temperature_c": FeatureProfile(50.0, 0.70),
            "energy_kwh": FeatureProfile(1.45, 0.12, drift_std=0.140),
        },
    ),
}

# Number of drift episodes per machine and where they start (fraction of the
# series) — deterministic base positions, jittered by the RNG.
EPISODE_STARTS = (0.33, 0.67)
EPISODE_LENGTH_RANGE = (100, 160)
EPISODE_DRIVER_AMPLITUDE_RANGE = (2.2, 3.0)  # x drift_std (p98 of normal)
EPISODE_SECONDARY_AMPLITUDE_RANGE = (1.2, 1.8)  # x drift_std
EPISODE_PERIOD_RANGE = (8, 16)  # oscillation period in cycles
EPISODE_NOISE_MULTIPLIER = 1.6
EPISODE_DRIFT_FRACTION = 0.3  # slow-drift ramp amplitude as a fraction of the wobble amplitude


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _clip(values: np.ndarray, feature: str) -> np.ndarray:
    """Clip a feature array to its global plausibility window."""
    low, high = PLAUSIBLE_BOUNDS[feature]
    return np.clip(values, low, high)


def _add_drift_episodes(values: dict[str, np.ndarray], profile: MachineProfile, rng: np.random.Generator) -> None:
    """Overlay slow-drift + oscillation episodes on the stable regimes.

    Each episode picks a driver feature and a secondary feature, then adds a
    bell-shaped envelope (instability grows, peaks, then fades) carrying a
    linear slow drift plus a sinusoidal wobble sized as a multiple of the
    normal rolling volatility (``drift_std``). Only the core of the episode
    exceeds the HDT thresholds — the edges stay below, which keeps the alert
    rate realistic while making the drift clearly visible in the raw series.
    """
    n = len(next(iter(values.values())))
    drivers = [f for f in DRIFT_DRIVERS if profile.features[f].drift_std > 0]
    for k, base_fraction in enumerate(EPISODE_STARTS):
        start = int(n * base_fraction) + int(rng.integers(-60, 61))
        length = int(rng.integers(*EPISODE_LENGTH_RANGE))
        start = max(60, min(start, n - length - 40))
        stop = start + length
        indices = np.arange(start, stop)
        t = (indices - start) / (length - 1)
        envelope = np.sin(np.pi * t) ** 0.8  # 0 at edges, 1 at the core

        driver = str(rng.choice(drivers))
        secondary = str(rng.choice([f for f in drivers if f != driver]))
        driver_amp = float(rng.uniform(*EPISODE_DRIVER_AMPLITUDE_RANGE)) * profile.features[driver].drift_std
        secondary_amp = float(rng.uniform(*EPISODE_SECONDARY_AMPLITUDE_RANGE)) * profile.features[secondary].drift_std
        period = int(rng.integers(*EPISODE_PERIOD_RANGE))
        phase = float(rng.uniform(0.0, 2.0 * np.pi))

        # Slow drift: linear ramp from -0.5*A to +0.5*A across the episode.
        ramp = np.linspace(-0.5, 0.5, length)
        # Oscillation on top of the ramp (unstable regime).
        wobble = np.sin(2.0 * np.pi * indices / period + phase)
        for feature, amp in ((driver, driver_amp), (secondary, secondary_amp)):
            noise_mult = EPISODE_NOISE_MULTIPLIER if feature == driver else 1.3
            base_noise = rng.normal(0.0, profile.features[feature].noise * noise_mult, size=length)
            values[feature][start:stop] += envelope * (
                amp * (EPISODE_DRIFT_FRACTION * ramp + 0.85 * wobble)
            ) + base_noise


def _add_scrap_flags(values: dict[str, np.ndarray], profile: MachineProfile, rng: np.random.Generator) -> np.ndarray:
    """Assign scrap_flag=1 on instability bursts and rare isolated scraps.

    Scrap bursts cluster inside drift episodes (the most unstable phase); a
    small isolated-scrap rate keeps the overall budget in the 2-5% range.
    """
    n = len(next(iter(values.values())))
    scrap = np.zeros(n, dtype=int)

    # Isolated scraps outside episodes (sensor/quality noise of daily life).
    isolated = rng.random(n) < SCRAP_ISOLATED_PROB
    scrap[isolated] = 1

    for k, base_fraction in enumerate(EPISODE_STARTS):
        start = int(n * base_fraction) + int(rng.integers(-60, 61))
        length = int(rng.integers(*EPISODE_LENGTH_RANGE))
        start = max(60, min(start, n - length - 40))
        # One or two scrap bursts in the second half of the episode.
        burst_anchor = start + int(length * rng.uniform(0.55, 0.85))
        for _ in range(int(rng.integers(1, 3))):
            burst_len = int(rng.integers(SCRAP_BURST_MIN, SCRAP_BURST_MAX + 1))
            burst_start = max(start, min(burst_anchor, n - burst_len))
            scrap[burst_start:burst_start + burst_len] = 1
    return scrap


def _build_timestamps(ref: str, n: int, rng: np.random.Generator) -> list[str]:
    """Regular cadence (30-90 s between cycles) as naive local timestamps."""
    profile = MACHINE_PROFILES[ref]
    start = EXPORT_START + pd.Timedelta(hours=EXPORT_STAGGER_HOURS[ref])
    timestamps: list[str] = []
    current = start
    for _ in range(n):
        timestamps.append(current.strftime("%Y-%m-%d %H:%M:%S.%f"))
        cadence = profile.cadence_base_s * float(rng.normal(1.0, 0.06))
        cadence = float(np.clip(cadence, MIN_CADENCE_S, MAX_CADENCE_S))
        current = current + pd.Timedelta(seconds=cadence)
    return timestamps


def generate_machine_cycles(ref: str, n_cycles: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate one machine's raw cycles export (stable regime + drift + scrap)."""
    profile = MACHINE_PROFILES[ref]
    values: dict[str, np.ndarray] = {}
    for feature, fprofile in profile.features.items():
        noise = rng.normal(0.0, fprofile.noise, size=n_cycles)
        values[feature] = _clip(fprofile.mean + noise, feature)

    _add_drift_episodes(values, profile, rng)
    scrap = _add_scrap_flags(values, profile, rng)

    # Drift episodes are overlaid after the initial clip: re-clip so every
    # value stays inside the global plausibility windows of the contract.
    values = {feature: _clip(values[feature], feature) for feature in profile.features}

    frame = pd.DataFrame({feature: np.round(values[feature], 3) for feature in profile.features})
    frame.insert(0, "machine_erp_ref", ref)
    frame.insert(0, "timestamp", _build_timestamps(ref, n_cycles, rng))
    frame["scrap_flag"] = scrap
    return frame[CONTRACT_COLUMNS]


def generate_dataset(seed: int = DEFAULT_SEED, n_cycles_per_machine: int = DEFAULT_CYCLES_PER_MACHINE) -> pd.DataFrame:
    """Generate the full raw export for every machine in the fleet."""
    rng = np.random.default_rng(seed)
    frames = [
        generate_machine_cycles(ref, n_cycles_per_machine, rng)
        for ref in MACHINE_PROFILES
    ]
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Persistence and scoring
# ---------------------------------------------------------------------------

def write_export(frame: pd.DataFrame, output_dir: Path) -> list[Path]:
    """Write one ``machine_cycles_bruts_<ref>.csv`` file per machine."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for ref, group in frame.groupby("machine_erp_ref", sort=False):
        path = output_dir / f"machine_cycles_bruts_{ref}.csv"
        group.to_csv(path, index=False)
        written.append(path)
    return written


def score_export(frame: pd.DataFrame, artifact_path: Path) -> dict[str, Any]:
    """Run the full HDT pipeline (prepare_inference_frame + predict)."""
    artifact = load_artifact(artifact_path)
    prepared = prepare_inference_frame(frame)
    predictions = predict(artifact, prepared)
    scores = predictions["anomaly_score"]
    alerts = predictions["predicted_instability_next_20_cycles"]
    return {
        "model_version": artifact["model_version"],
        "artifact": str(artifact_path),
        "nb_cycles": int(len(prepared)),
        "nb_alertes": int(alerts.sum()),
        "alert_rate": float(alerts.mean()),
        "score_min": float(scores.min()),
        "score_max": float(scores.max()),
        "score_mean": float(scores.mean()),
        "threshold_min": float(predictions["threshold"].min()),
        "threshold_max": float(predictions["threshold"].max()),
        "machines": sorted(frame["machine_erp_ref"].astype(str).unique().tolist()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic simulated raw cycles export for the HDT model"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (default: 42)")
    parser.add_argument("--cycles-per-machine", type=int, default=DEFAULT_CYCLES_PER_MACHINE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--score",
        action="store_true",
        help="Score the generated export through the HDT artifact (prepare_inference_frame + predict)",
    )
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()

    frame = generate_dataset(seed=args.seed, n_cycles_per_machine=args.cycles_per_machine)
    written = write_export(frame, args.output_dir)

    summary: dict[str, Any] = {
        "seed": args.seed,
        "files": [str(path) for path in written],
        "nb_cycles": int(len(frame)),
        "nb_cycles_par_machine": {
            str(ref): int(count) for ref, count in frame.groupby("machine_erp_ref").size().items()
        },
        "scrap_rate": float(frame["scrap_flag"].mean()),
        "scrap_cycles": int(frame["scrap_flag"].sum()),
        "timestamp_min": str(frame["timestamp"].min()),
        "timestamp_max": str(frame["timestamp"].max()),
    }
    if args.score:
        summary["hdt"] = score_export(frame, args.artifact)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
