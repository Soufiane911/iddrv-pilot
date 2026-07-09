from datetime import datetime, timedelta, timezone

import pytest

from backend.app.diagnostics import DiagnosticEngine, InMemoryDiagnosticRepository, InsufficientDataError


UTC = timezone.utc
START = datetime(2025, 2, 12, 0, 20, tzinfo=UTC)
END = datetime(2025, 2, 12, 1, 50, tzinfo=UTC)


def row(ts, temp, scrap=False, defect=None):
    return {"timestamp": ts, "machine_erp_ref": "152", "barrel_temp_zone2_c": temp,
            "scrap_flag": scrap, "defect_type": defect}


def test_s001_returns_recalculated_evidence_and_temperature_hypothesis():
    cycles = [row(START - timedelta(minutes=10), 210), row(START - timedelta(minutes=5), 211)]
    cycles += [row(START + timedelta(minutes=10), 195, True, "short_shot"), row(START + timedelta(minutes=20), 194, True, "short_shot"), row(START + timedelta(minutes=30), 196)]
    repo = InMemoryDiagnosticRepository(
        cycles=cycles,
        quality_checks=[{**row(START + timedelta(minutes=30), 195), "quality_check_id": "QC-1", "defect_type": "short_shot", "defect_count": 2}],
        operator_notes=[{"timestamp": START + timedelta(minutes=20), "machine_erp_ref": "152", "production_order_id": "OF-2025-0012", "note_id": "NOTE-1", "note_text": "Zone 2 sous le seuil nominal"}],
    )
    result = DiagnosticEngine(repo).investigate(machine_id=152, machine_erp_ref="152", production_order_id="OF-2025-0012", started_at=START, ended_at=END)
    assert result.incident["symptom"] == "short_shot_increase"
    assert result.hypotheses[0].cause_code == "low_barrel_temperature_zone_2"
    assert any(e.metric == "barrel_temp_zone2_c" and e.baseline["value"] == 210.5 for e in result.evidence)
    assert any(e.source_kind == "operator_note" for e in result.evidence)
    assert all("ground_truth" not in repr(e).lower() for e in result.evidence)


def test_s001_marks_missing_baseline_without_inventing_it():
    repo = InMemoryDiagnosticRepository(cycles=[row(START + timedelta(minutes=5), 195, True, "short_shot")])
    result = DiagnosticEngine(repo).investigate(machine_id=152, production_order_id="OF-2025-0012", started_at=START, ended_at=END)
    assert result.data_quality == "insufficient_baseline"
    assert "baseline_cycles" in result.hypotheses[0].missing_data
    temp = next(e for e in result.evidence if e.metric == "barrel_temp_zone2_c")
    assert temp.baseline is None


def test_s001_rejects_empty_window():
    with pytest.raises(InsufficientDataError):
        DiagnosticEngine(InMemoryDiagnosticRepository()).investigate(machine_id=152, production_order_id="OF-1", started_at=START, ended_at=END)
