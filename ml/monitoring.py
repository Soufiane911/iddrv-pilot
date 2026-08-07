"""Drift and calibration monitoring for the HDT process-drift model.

The HDT anomaly score is an *uncalibrated ranking score* (see
ml/VALIDATION-HDT.md: average precision 0.14, ROC AUC 0.878, "an alert is not a
probability"). This module therefore monitors three separate concerns:

1. Distribution shift of the raw score against a reference distribution, using
   the Population Stability Index (PSI) and, as a complement, the two-sample
   Kolmogorov-Smirnov test (scipy.stats.ks_2samp).

   Reference method (documented choice): the deployed artifact
   (models/process_drift_hdt_v1.joblib) and its meta.json do not persist a score
   distribution; meta.json only stores aggregate metrics such as the test
   alert_rate. The reference is therefore built as the empirical distribution of
   anomaly scores produced by the *deployed artifact itself* over the same
   population it was trained on: historical cycles with scrap_flag == 0 (the
   artifact's documented `normal_training_population`), deterministically
   sub-sampled to at most 5000 cycles. When that data is not reachable at
   runtime, a documented parametric fallback is used: an exponential reference
   whose upper tail P(score >= global_threshold) equals 1 -
   NORMAL_SCORE_QUANTILE (0.02), i.e. consistent with the training-time
   threshold definition (98th percentile of normal scores).

2. Alert rate: the fraction of predictions whose score reaches the
   machine-specific threshold. Each observation carries its own threshold, so
   machine-contextualized thresholds are respected.

3. Calibration, only when the real outcome arrives later. Because the raw score
   is not a probability, each score is first mapped to a rank-based probability
   p = F_hat_ref(score), the empirical CDF of the reference distribution at the
   observed score. Brier score = mean((p - y)^2) and a simple equal-width
   binning of p (default 5 bins) give the calibration curve statistics. The
   caller provides the observed binary outcome (scrap_flag), consistent with the
   HDT label contract (instability = at least MIN_FUTURE_SCRAPS = 3 scraps in
   the next HORIZON_CYCLES = 20 cycles); the monitor itself only needs the
   binary outcome.

All state is held in memory and guarded by a single reentrant lock; `reset()`
clears it so tests start from a clean slate.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

LOGGER = logging.getLogger("iddrv.monitoring")

DEFAULT_SCORE_BINS = 10
DEFAULT_CALIBRATION_BINS = 5
DEFAULT_WINDOW = 10_000
EPSILON = 1e-6
MIN_REFERENCE_SAMPLES = 100
MAX_REFERENCE_SAMPLES = 5_000
REFERENCE_BOOTSTRAP_SAMPLES = 5_000


@dataclass(frozen=True)
class KsResult:
    """Two-sample Kolmogorov-Smirnov result (scipy-version independent)."""

    statistic: float
    pvalue: float


class DriftMonitor:
    """Thread-safe, in-memory drift/alert-rate/calibration tracker for HDT scores.

    The reference distribution is fixed at construction time; observed scores
    accumulate in a bounded recent window. Feedback pairs (score, scrap_flag)
    are kept separately so calibration can be computed once real labels arrive.
    """

    def __init__(
        self,
        reference_scores: Sequence[float] | np.ndarray,
        *,
        score_bins: int = DEFAULT_SCORE_BINS,
        calibration_bins: int = DEFAULT_CALIBRATION_BINS,
        window: int = DEFAULT_WINDOW,
    ) -> None:
        reference = np.asarray(reference_scores, dtype=float)
        reference = reference[np.isfinite(reference)].copy()
        if len(reference) < 2:
            raise ValueError("reference_scores must contain at least 2 finite values")
        if score_bins < 2:
            raise ValueError("score_bins must be >= 2")
        if calibration_bins < 2:
            raise ValueError("calibration_bins must be >= 2")
        if window < 1:
            raise ValueError("window must be >= 1")
        self._reference = reference
        self._score_bins = int(score_bins)
        self._calibration_bins = int(calibration_bins)
        self._window = int(window)
        self._lock = threading.RLock()
        self._scores: deque[float] = deque(maxlen=self._window)
        self._alerts: deque[bool] = deque(maxlen=self._window)
        self._feedback: deque[tuple[float, int]] = deque(maxlen=self._window)
        self._total_observations = 0
        self._total_alerts = 0

    # -- ingestion -----------------------------------------------------------

    def observe(self, score: float, *, threshold: float | None = None) -> bool:
        """Record one prediction score; returns whether it reached the threshold.

        Defensive by design: non-finite or non-numeric input is ignored and
        reported as non-alert so that monitoring can never break the prediction
        path.
        """
        try:
            value = float(score)
            if not math.isfinite(value):
                return False
        except (TypeError, ValueError):
            return False
        alert = False
        if threshold is not None:
            try:
                alert = value >= float(threshold)
            except (TypeError, ValueError):
                alert = False
        with self._lock:
            self._scores.append(value)
            self._alerts.append(alert)
            self._total_observations += 1
            if alert:
                self._total_alerts += 1
        return alert

    def update_feedback(self, score: float, scrap_flag: int | bool | float) -> None:
        """Attach the observed binary outcome to a past prediction score.

        `scrap_flag` must be 0 or 1 (bool accepted). The raw score is stored;
        the rank-based probability is derived at read time so the reference
        remains the single source of truth for the mapping.
        """
        if isinstance(scrap_flag, bool):
            label = int(scrap_flag)
        elif isinstance(scrap_flag, (int, float)) and float(scrap_flag) in (0.0, 1.0):
            label = int(scrap_flag)
        else:
            raise ValueError(f"scrap_flag must be 0 or 1, got {scrap_flag!r}")
        try:
            value = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"score must be a float, got {score!r}") from exc
        if not math.isfinite(value):
            raise ValueError(f"score must be finite, got {score!r}")
        with self._lock:
            self._feedback.append((value, label))

    # -- distribution shift --------------------------------------------------

    def _psi_between(self, reference: np.ndarray, observed: np.ndarray) -> float:
        """PSI between two empirical distributions on shared reference bins."""
        if len(reference) == 0 or len(observed) == 0:
            return 0.0
        low = float(np.min(reference))
        high = float(np.max(reference))
        if high <= low:
            return 0.0
        raw_edges = np.quantile(reference, np.linspace(0.0, 1.0, self._score_bins + 1))
        edges = np.unique(raw_edges)
        if len(edges) < 2:
            return 0.0
        edges[0] = low
        edges[-1] = high
        expected = np.histogram(np.clip(reference, low, high), bins=edges)[0] / len(reference)
        actual = np.histogram(np.clip(observed, low, high), bins=edges)[0] / len(observed)
        # Smoothing avoids log(0) when a bin is empty on either side.
        expected = np.clip(expected, EPSILON, None)
        actual = np.clip(actual, EPSILON, None)
        return float(np.sum((actual - expected) * np.log(actual / expected)))

    def psi(self, scores: Sequence[float] | np.ndarray | None = None) -> float:
        """PSI of the recent window (or of `scores` when provided) vs reference.

        Conventional reading: < 0.1 stable, 0.1-0.25 moderate shift, > 0.25
        significant shift. Thresholds are indicative for this approximation.
        """
        if scores is None:
            with self._lock:
                observed = np.asarray(list(self._scores), dtype=float)
        else:
            observed = np.asarray(scores, dtype=float)
        observed = observed[np.isfinite(observed)]
        return self._psi_between(self._reference, observed)

    def ks_test(self, scores: Sequence[float] | np.ndarray | None = None) -> KsResult:
        """Two-sample Kolmogorov-Smirnov test of the recent window vs reference."""
        from scipy.stats import ks_2samp

        if scores is None:
            with self._lock:
                observed = np.asarray(list(self._scores), dtype=float)
        else:
            observed = np.asarray(scores, dtype=float)
        observed = observed[np.isfinite(observed)]
        if len(observed) == 0 or len(self._reference) == 0:
            return KsResult(statistic=0.0, pvalue=1.0)
        result = ks_2samp(observed, self._reference)
        return KsResult(statistic=float(result.statistic), pvalue=float(result.pvalue))

    # -- alert rate ----------------------------------------------------------

    def alert_rate(self) -> float:
        """Fraction of predictions above threshold over the recent window."""
        with self._lock:
            if not self._alerts:
                return 0.0
            return float(sum(self._alerts)) / len(self._alerts)

    # -- calibration ---------------------------------------------------------

    def _probability(self, score: float) -> float:
        """Rank-based probability: empirical CDF of the reference at the score."""
        return float(np.mean(self._reference <= score))

    def brier_score(self) -> float | None:
        """Brier score on rank-mapped probabilities; None until feedback exists."""
        with self._lock:
            pairs = list(self._feedback)
        if not pairs:
            return None
        probabilities = np.asarray([self._probability(score) for score, _ in pairs], dtype=float)
        labels = np.asarray([label for _, label in pairs], dtype=float)
        return float(np.mean((probabilities - labels) ** 2))

    def calibration_stats(self) -> list[dict[str, Any]]:
        """Equal-width binning of rank-mapped probabilities vs observed rates."""
        with self._lock:
            pairs = list(self._feedback)
        if not pairs:
            return []
        probabilities = np.asarray([self._probability(score) for score, _ in pairs], dtype=float)
        labels = np.asarray([label for _, label in pairs], dtype=float)
        stats: list[dict[str, Any]] = []
        for index in range(self._calibration_bins):
            lower = index / self._calibration_bins
            upper = (index + 1) / self._calibration_bins
            mask = (probabilities >= lower) & (probabilities < upper)
            if index == self._calibration_bins - 1:
                mask |= probabilities == 1.0
            count = int(mask.sum())
            if count == 0:
                stats.append(
                    {
                        "bin": index,
                        "lower": lower,
                        "upper": upper,
                        "count": 0,
                        "mean_predicted": None,
                        "observed_rate": None,
                    }
                )
            else:
                stats.append(
                    {
                        "bin": index,
                        "lower": lower,
                        "upper": upper,
                        "count": count,
                        "mean_predicted": float(np.mean(probabilities[mask])),
                        "observed_rate": float(np.mean(labels[mask])),
                    }
                )
        return stats

    # -- state ---------------------------------------------------------------

    @property
    def reference_size(self) -> int:
        return len(self._reference)

    @property
    def observation_count(self) -> int:
        with self._lock:
            return self._total_observations

    @property
    def alert_count(self) -> int:
        with self._lock:
            return self._total_alerts

    @property
    def feedback_count(self) -> int:
        with self._lock:
            return len(self._feedback)

    @property
    def recent_count(self) -> int:
        with self._lock:
            return len(self._scores)

    def reset(self) -> None:
        """Clear all observed state (scores, alerts, feedback, counters)."""
        with self._lock:
            self._scores.clear()
            self._alerts.clear()
            self._feedback.clear()
            self._total_observations = 0
            self._total_alerts = 0

    def snapshot(self) -> dict[str, Any]:
        """Consistent point-in-time view for dashboards and logs."""
        ks = self.ks_test()
        return {
            "reference_size": self.reference_size,
            "observations_total": self.observation_count,
            "alerts_total": self.alert_count,
            "recent_window": self.recent_count,
            "alert_rate": self.alert_rate(),
            "psi": self.psi(),
            "ks_statistic": float(ks.statistic),
            "ks_pvalue": float(ks.pvalue),
            "brier_score": self.brier_score(),
            "calibration": self.calibration_stats(),
        }


def build_reference_scores(
    artifact: dict[str, Any],
    cycles_dir: str | Path | None = None,
    *,
    max_samples: int = MAX_REFERENCE_SAMPLES,
) -> np.ndarray:
    """Empirical reference score distribution from the normal training population.

    Scores the cycles with scrap_flag == 0 (the documented normal training
    population) with the *deployed* artifact, then sub-samples deterministically
    (stride) to at most `max_samples` cycles. Raises when no normal cycles are
    reachable; callers decide whether to fall back to the bootstrap reference.
    """
    from ml.process_drift import load_cycle_files, predict, prepare_inference_frame

    directory = Path(cycles_dir) if cycles_dir is not None else Path(
        os.getenv("PROCESS_DRIFT_REFERENCE_DATA", "data/scenarios/industrial_demo")
    )
    frame = load_cycle_files(directory)
    normal = frame[frame["scrap_flag"] == 0]
    if normal.empty:
        raise ValueError("no normal (scrap_flag == 0) cycles available for the reference")
    if len(normal) > max_samples:
        step = len(normal) // max_samples
        normal = normal.iloc[::step].head(max_samples)
    prepared = prepare_inference_frame(normal)
    scores = predict(artifact, prepared)["anomaly_score"].to_numpy(dtype=float)
    scores = scores[np.isfinite(scores)]
    if len(scores) < MIN_REFERENCE_SAMPLES:
        raise ValueError("reference score distribution is too small")
    return scores


def _bootstrap_reference(
    global_threshold: float,
    n: int = REFERENCE_BOOTSTRAP_SAMPLES,
    seed: int = 42,
) -> np.ndarray:
    """Parametric fallback reference: exponential tail anchored on the threshold.

    The training-time threshold is the NORMAL_SCORE_QUANTILE (0.98) quantile of
    normal scores, so the fallback reference is an exponential distribution with
    P(score >= global_threshold) = 1 - NORMAL_SCORE_QUANTILE = 0.02. This is an
    approximation used only when the training population is not reachable.
    """
    from ml.process_drift import NORMAL_SCORE_QUANTILE

    threshold = float(global_threshold)
    if not math.isfinite(threshold) or threshold <= 0.0:
        threshold = 1.0
    rate = -math.log(1.0 - NORMAL_SCORE_QUANTILE) / threshold
    rng = np.random.default_rng(seed)
    return rng.exponential(scale=1.0 / rate, size=n)


_MONITOR_LOCK = threading.RLock()
_MONITOR: DriftMonitor | None = None


def _default_reference() -> np.ndarray:
    """Reference for the deployed artifact: real normal scores, else bootstrap."""
    artifact: dict[str, Any] | None = None
    try:
        from ml.process_drift import load_artifact

        artifact_path = Path(os.getenv("PROCESS_DRIFT_MODEL_PATH", "models/process_drift_hdt_v1.joblib"))
        if artifact_path.is_file():
            artifact = load_artifact(artifact_path)
            return build_reference_scores(artifact)
    except Exception as exc:  # noqa: BLE001 - monitoring must degrade gracefully
        LOGGER.warning("reference score distribution unavailable, using bootstrap fallback: %s", exc)
    threshold = 1.0
    if artifact is not None:
        try:
            threshold = float(artifact.get("global_threshold", 1.0))
        except (TypeError, ValueError):
            threshold = 1.0
    return _bootstrap_reference(threshold)


def get_monitor() -> DriftMonitor:
    """Process-wide drift monitor, built lazily and cached (thread-safe)."""
    global _MONITOR
    with _MONITOR_LOCK:
        if _MONITOR is None:
            _MONITOR = DriftMonitor(reference_scores=_default_reference())
        return _MONITOR


def reset_monitor() -> None:
    """Drop the process-wide monitor (tests) so the next call rebuilds it."""
    global _MONITOR
    with _MONITOR_LOCK:
        _MONITOR = None


def record_prediction(score: float, *, threshold: float | None = None) -> None:
    """Feed one successful prediction into the process-wide monitor.

    Never raises: the prediction API must not be affected by monitoring.
    """
    try:
        get_monitor().observe(score, threshold=threshold)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("failed to record process-drift prediction for monitoring: %s", exc)
