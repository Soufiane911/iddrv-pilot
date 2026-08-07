"""Drift/calibration monitoring tests for the HDT model.

Covers ml.monitoring (PSI/KS shift detection, alert rate, Brier score and
calibration binning on real labels, thread-safety, reset) and the Prometheus
integration wired into POST /api/v1/process-drift.
"""

import re
import threading
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.api import process_drift
from backend.app.main import app
from backend.app.security import Identity, create_session_token
from ml import monitoring

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_monitoring_state():
    # Reset after each test so the process-wide singleton and the model cache
    # never leak state across tests, while consecutive tests still share a build.
    yield
    monitoring.reset_monitor()
    process_drift._model_artifact.cache_clear()


def _headers(identity: Identity) -> dict[str, str]:
    token, _ = create_session_token(identity)
    return {"Authorization": f"Bearer {token}"}


def _viewer(site_ids: tuple[int, ...] = (1,)) -> Identity:
    return Identity("u1", "u@test", "User", "viewer", site_ids, session_id="sid-1")


def _cycle(index: int, machine_erp_ref: str = "1003") -> dict[str, object]:
    return {
        "timestamp": (datetime(2025, 2, 17, tzinfo=timezone.utc) + timedelta(minutes=index)).isoformat(),
        "machine_erp_ref": machine_erp_ref,
        "cycle_time_s": 30.0 + index * 0.2,
        "dosing_time_s": 7.2 + index * 0.02,
        "injection_time_s": 2.9 + index * 0.03,
        "cooling_time_s": 15.0 + index * 0.1,
        "cushion_mm": 4.5 + index * 0.01,
        "switchover_position_mm": 17.0 + index * 0.02,
        "switchover_pressure_bar": 165.0 + index * 0.2,
        "peak_pressure_bar": 840.0 + index * 1.5,
        "clamp_force_kn": 1450.0 + index,
        "mold_temperature_c": 54.0 + index * 0.1,
        "barrel_temp_zone1_c": 203.0 + index * 0.1,
        "barrel_temp_zone2_c": 224.0 + index * 0.2,
        "barrel_temp_zone3_c": 214.0 + index * 0.1,
        "oil_temperature_c": 51.0 + index * 0.1,
        "energy_kwh": 1.0 + index * 0.01,
    }


def _payload() -> dict[str, object]:
    return {"site_id": 1, "cycles": [_cycle(index) for index in range(3)]}


def _metric_value(metrics_text: str, metric_name: str) -> float:
    """Parse the plain-text Prometheus exposition for one metric value."""
    for line in metrics_text.splitlines():
        if line.startswith(metric_name + " ") or line.startswith(metric_name + "{"):
            return float(line.rsplit(" ", 1)[-1])
    return 0.0


# -- distribution shift (PSI / KS) -------------------------------------------


def test_psi_detects_artificial_distribution_shift():
    rng = np.random.default_rng(42)
    reference = rng.normal(loc=0.0, scale=1.0, size=5000)
    monitor = monitoring.DriftMonitor(reference_scores=reference)

    for score in reference[:2000]:
        monitor.observe(float(score), threshold=2.0)
    assert monitor.psi() < 0.1  # same distribution -> stable

    monitor.reset()
    shifted = rng.normal(loc=3.0, scale=1.0, size=2000)
    for score in shifted:
        monitor.observe(float(score), threshold=2.0)
    assert monitor.psi() > 0.25  # conventional significant-shift threshold
    # 15.9% of N(3,1) stays below the threshold: the alert rate must reflect that.
    assert monitor.alert_rate() == pytest.approx(float((shifted >= 2.0).mean()))


def test_ks_detects_artificial_distribution_shift():
    rng = np.random.default_rng(7)
    reference = rng.normal(loc=0.0, scale=1.0, size=3000)
    monitor = monitoring.DriftMonitor(reference_scores=reference)

    result = monitor.ks_test(scores=reference[:500])
    assert result.pvalue > 0.01

    shifted = rng.normal(loc=2.5, scale=1.0, size=500)
    result = monitor.ks_test(scores=shifted)
    assert result.statistic > 0.3
    assert result.pvalue < 1e-9


def test_psi_and_ks_accept_explicit_scores_without_state_change():
    rng = np.random.default_rng(11)
    reference = rng.normal(size=3000)
    monitor = monitoring.DriftMonitor(reference_scores=reference)

    assert monitor.psi(scores=reference[:500]) < 0.1
    assert monitor.ks_test(scores=reference[:500]).pvalue > 0.01

    shifted = rng.normal(loc=2.5, size=500)
    assert monitor.psi(scores=shifted) > 0.25
    assert monitor.ks_test(scores=shifted).pvalue < 1e-9

    assert monitor.observation_count == 0
    assert monitor.recent_count == 0


# -- calibration (Brier + binning) -------------------------------------------


def test_brier_score_known_case():
    reference = [0.0, 0.25, 0.5, 0.75, 1.0]
    monitor = monitoring.DriftMonitor(reference_scores=reference)
    pairs = [(0.5, 1), (0.5, 0), (0.25, 1), (1.0, 0)]
    for score, label in pairs:
        monitor.update_feedback(score, label)

    # Rank mapping p = F_ref(x) = mean(reference <= x):
    #   0.5 -> 3/5 = 0.6 ; 0.25 -> 2/5 = 0.4 ; 1.0 -> 1.0
    # Brier = ((0.6-1)^2 + (0.6-0)^2 + (0.4-1)^2 + (1.0-0)^2) / 4 = 1.88 / 4
    assert monitor.brier_score() == pytest.approx(0.47)


def test_calibration_stats_known_case():
    reference = [0.0, 0.25, 0.5, 0.75, 1.0]
    monitor = monitoring.DriftMonitor(reference_scores=reference, calibration_bins=5)
    for score, label in [(0.5, 1), (0.5, 0), (0.25, 1), (1.0, 0)]:
        monitor.update_feedback(score, label)

    stats = monitor.calibration_stats()
    by_bin = {entry["bin"]: entry for entry in stats}

    # p = 0.6 twice (scores 0.5), labels 1 and 0 -> bin 3 (0.6 <= p < 0.8)
    assert by_bin[3]["count"] == 2
    assert by_bin[3]["mean_predicted"] == pytest.approx(0.6)
    assert by_bin[3]["observed_rate"] == pytest.approx(0.5)

    # p = 0.4 (score 0.25), label 1 -> bin 2
    assert by_bin[2]["count"] == 1
    assert by_bin[2]["observed_rate"] == pytest.approx(1.0)

    # p = 1.0 (score 1.0), label 0 -> last bin, inclusive upper edge
    assert by_bin[4]["count"] == 1
    assert by_bin[4]["mean_predicted"] == pytest.approx(1.0)
    assert by_bin[4]["observed_rate"] == pytest.approx(0.0)

    assert by_bin[0]["count"] == 0
    assert by_bin[0]["observed_rate"] is None


def test_update_feedback_rejects_invalid_labels():
    monitor = monitoring.DriftMonitor(reference_scores=[0.0, 1.0])
    with pytest.raises(ValueError, match="scrap_flag"):
        monitor.update_feedback(0.5, 2)
    with pytest.raises(ValueError, match="scrap_flag"):
        monitor.update_feedback(0.5, 0.5)
    with pytest.raises(ValueError, match="finite"):
        monitor.update_feedback(float("nan"), 1)
    assert monitor.feedback_count == 0
    monitor.update_feedback(0.5, True)  # bool accepted
    monitor.update_feedback(0.5, 0)
    assert monitor.feedback_count == 2


# -- thread safety -----------------------------------------------------------


def test_monitor_is_thread_safe():
    rng = np.random.default_rng(3)
    reference = rng.normal(size=3000)
    monitor = monitoring.DriftMonitor(reference_scores=reference)
    per_thread = 250
    observe_scores = rng.normal(size=4 * per_thread)
    feedback_scores = rng.normal(size=4 * per_thread)

    def observe_worker(worker: int) -> None:
        for index in range(per_thread):
            monitor.observe(float(observe_scores[worker * per_thread + index]), threshold=1.0)

    def feedback_worker(worker: int) -> None:
        for index in range(per_thread):
            label = 1 if index % 3 == 0 else 0
            monitor.update_feedback(float(feedback_scores[worker * per_thread + index]), label)

    threads = [threading.Thread(target=observe_worker, args=(worker,)) for worker in range(4)]
    threads += [threading.Thread(target=feedback_worker, args=(worker,)) for worker in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    expected_observations = 4 * per_thread
    expected_alerts = int((observe_scores >= 1.0).sum())
    assert monitor.observation_count == expected_observations
    assert monitor.alert_count == expected_alerts
    assert monitor.recent_count == expected_observations
    assert monitor.feedback_count == expected_observations
    assert monitor.alert_rate() == pytest.approx(expected_alerts / expected_observations)
    assert monitor.psi() >= 0.0  # computed without error under contention
    assert 0.0 <= monitor.ks_test().pvalue <= 1.0

    # Brier must match a single-threaded monitor fed the same feedback pairs.
    sequential = monitoring.DriftMonitor(reference_scores=reference)
    for worker in range(4):
        for index in range(per_thread):
            label = 1 if index % 3 == 0 else 0
            sequential.update_feedback(float(feedback_scores[worker * per_thread + index]), label)
    assert monitor.brier_score() == pytest.approx(sequential.brier_score())


# -- reset -------------------------------------------------------------------


def test_reset_clears_monitor_state():
    monitor = monitoring.DriftMonitor(reference_scores=[0.0, 0.5, 1.0])
    monitor.observe(1.0, threshold=0.5)
    monitor.observe(0.1, threshold=0.5)
    monitor.update_feedback(1.0, 1)
    assert monitor.observation_count == 2
    assert monitor.alert_count == 1
    assert monitor.feedback_count == 1

    monitor.reset()
    assert monitor.observation_count == 0
    assert monitor.alert_count == 0
    assert monitor.feedback_count == 0
    assert monitor.recent_count == 0
    assert monitor.alert_rate() == 0.0
    assert monitor.psi() == 0.0
    assert monitor.ks_test().pvalue == 1.0
    assert monitor.brier_score() is None
    assert monitor.calibration_stats() == []


# -- process-wide singleton --------------------------------------------------


def test_record_prediction_never_raises_and_feeds_singleton():
    monitoring.reset_monitor()
    monitoring.record_prediction(score=float("nan"), threshold=0.5)  # ignored
    monitoring.record_prediction(score=0.75, threshold=0.5)

    monitor = monitoring.get_monitor()
    assert monitor.observation_count == 1
    assert monitor.alert_count == 1
    assert monitor.reference_size >= monitoring.MIN_REFERENCE_SAMPLES


def test_module_singleton_is_lazy_resettable_and_shared():
    monitoring.reset_monitor()
    first = monitoring.get_monitor()
    second = monitoring.get_monitor()
    assert first is second

    monitoring.reset_monitor()
    assert monitoring.get_monitor() is not first


def test_bootstrap_reference_fallback_when_data_unreachable(monkeypatch):
    monkeypatch.setenv("PROCESS_DRIFT_REFERENCE_DATA", "nonexistent_reference_dir_xyz")
    monitoring.reset_monitor()
    monitor = monitoring.get_monitor()
    assert monitor.reference_size == monitoring.REFERENCE_BOOTSTRAP_SAMPLES
    assert monitor.psi() == 0.0  # empty window, no crash


# -- Prometheus integration through the API ----------------------------------


def test_prometheus_metrics_updated_after_process_drift_api_call():
    before = client.get("/metrics").text
    response = client.post("/api/v1/process-drift", headers=_headers(_viewer()), json=_payload())
    assert response.status_code == 200
    after = client.get("/metrics").text

    alert_fired = bool(response.json()["predicted_instability_next_20_cycles"])

    assert _metric_value(after, "iddrv_process_drift_predictions_total") - _metric_value(before, "iddrv_process_drift_predictions_total") == 1.0
    assert _metric_value(after, "iddrv_process_drift_score_count") - _metric_value(before, "iddrv_process_drift_score_count") == 1.0
    assert _metric_value(after, "iddrv_process_drift_inference_seconds_count") - _metric_value(before, "iddrv_process_drift_inference_seconds_count") == 1.0
    assert _metric_value(after, "iddrv_process_drift_alerts_total") - _metric_value(before, "iddrv_process_drift_alerts_total") == (1.0 if alert_fired else 0.0)
    assert "iddrv_process_drift_score_bucket" in after


def test_alert_counter_increments_when_alert_fired():
    from backend.app import metrics as backend_metrics

    before = _metric_value(client.get("/metrics").text, "iddrv_process_drift_alerts_total")
    backend_metrics.record_process_drift_prediction(score=7.5, alert=True, duration_s=0.01)
    after = _metric_value(client.get("/metrics").text, "iddrv_process_drift_alerts_total")
    assert after - before == 1.0


def test_process_drift_metrics_do_not_leak_business_labels():
    # The drift metrics must carry no business labels (no machine/site/erp
    # identifiers); only the histogram's standard `le` bucket label is allowed.
    response = client.post("/api/v1/process-drift", headers=_headers(_viewer()), json=_payload())
    assert response.status_code == 200
    body = client.get("/metrics").text
    for line in body.splitlines():
        if line.startswith("iddrv_process_drift_"):
            match = re.search(r"\{([^}]*)\}", line)
            if match:
                keys = [part.split("=", 1)[0] for part in match.group(1).split(",") if "=" in part]
                assert set(keys) <= {"le"}, f"drift metric must only carry the le label: {line}"
