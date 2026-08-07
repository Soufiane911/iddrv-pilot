from datetime import datetime, timedelta, timezone

from backend.app.diagnostics.runtime import detect_scrap_windows


def _row(index: int, scrap: bool):
    return {
        "time": datetime(2026, 7, 10, tzinfo=timezone.utc) + timedelta(seconds=index),
        "machine_id": 7,
        "production_order_id": "OF-1",
        "scrap_flag": scrap,
        "part_quality_status": "scrap" if scrap else "good",
        "defect_type": "short_shot" if scrap else None,
    }


def test_detector_requires_thirty_incident_and_baseline_cycles():
    assert detect_scrap_windows([_row(i, i >= 29) for i in range(59)]) == []


def test_detector_finds_scrap_increase_without_scenario_identifier():
    rows = [_row(i, False) for i in range(30)] + [_row(i + 30, i < 20) for i in range(30)]
    windows = detect_scrap_windows(rows)
    assert len(windows) == 1
    assert windows[0].baseline_rate == 0
    assert windows[0].incident_rate > 0.6
    assert windows[0].defect_type == "short_shot"


def test_detector_does_not_flag_healthy_window():
    rows = [_row(i, i % 25 == 0) for i in range(90)]
    assert detect_scrap_windows(rows) == []
