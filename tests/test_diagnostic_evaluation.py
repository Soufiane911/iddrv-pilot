from datetime import datetime, timedelta, timezone

import pytest

from backend.app.diagnostics import DeterministicInvestigator, InMemoryDiagnosticRepository, InsufficientDataError


def test_deterministic_investigator_abstains_on_sparse_window():
    start = datetime(2025, 2, 12, tzinfo=timezone.utc)
    repo = InMemoryDiagnosticRepository(
        cycles=[{"timestamp": start + timedelta(minutes=1), "scrap_flag": True, "defect_type": "short_shot"}],
    )
    investigator = DeterministicInvestigator(repo, minimum_event_cycles=30, minimum_quality_checks=2)
    with pytest.raises(InsufficientDataError):
        investigator.investigate(
            machine_id=152,
            production_order_id="OF-1",
            started_at=start,
            ended_at=start + timedelta(hours=1),
            defect_type="short_shot",
        )


def test_investigator_emits_resolvable_evidence_and_two_ranked_candidates():
    start = datetime(2025, 2, 12, tzinfo=timezone.utc)
    cycles = [
        {
            "timestamp": start - timedelta(minutes=minute),
            "machine_erp_ref": "152",
            "barrel_temp_zone2_c": 210 + (minute % 2),
            "scrap_flag": False,
        }
        for minute in range(1, 31)
    ] + [
        {"timestamp": start + timedelta(minutes=i), "machine_erp_ref": "152", "barrel_temp_zone2_c": 195, "scrap_flag": i < 8, "defect_type": "short_shot"}
        for i in range(1, 41)
    ]
    result = DeterministicInvestigator(
        InMemoryDiagnosticRepository(cycles=cycles),
        minimum_event_cycles=30,
        minimum_quality_checks=1,
    ).investigate(
        machine_id=152,
        production_order_id="OF-1",
        started_at=start,
        ended_at=start + timedelta(hours=1),
        defect_type="short_shot",
    )
    ids = {item.id for item in result.evidence}
    assert result.hypotheses
    assert len(result.hypotheses) <= 2
    assert all(set(item.supporting_evidence_ids) <= ids for item in result.hypotheses)

    second = DeterministicInvestigator(
        InMemoryDiagnosticRepository(cycles=cycles),
        minimum_event_cycles=30,
        minimum_baseline_cycles=30,
        minimum_quality_checks=1,
    ).investigate(
        machine_id=152,
        production_order_id="OF-1",
        started_at=start,
        ended_at=start + timedelta(hours=1),
        defect_type="short_shot",
    )
    assert ids.isdisjoint({item.id for item in second.evidence})
