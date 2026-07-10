"""Evaluation-only runner for the six industrial demo scenarios.

This module is intentionally outside ``backend``.  It is the only application
code allowed to read ``ground_truth.json``; runtime API/worker code never
imports it.  The evaluator is read-only: it resolves machine ids and feeds
bounded PostgreSQL rows to the deterministic investigator without inserting
incidents or diagnostic runs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import psycopg2

from backend.app.diagnostics import DeterministicInvestigator
from backend.app.diagnostics.postgres import PostgresDiagnosticRepository
from backend.app.diagnostics.models import InsufficientDataError


GROUND_TRUTH = Path(__file__).parents[1] / "data" / "scenarios" / "industrial_demo" / "ground_truth.json"
EXPECTED_CAUSES = {
    "S001": "low_barrel_temperature_zone_2",
    "S002": "high_injection_pressure_low_clamp_force",
    "S003": "unstable_cooling_mold_temperature",
    "S004": "material_change_incomplete_purge",
    "S005": "restart_thermal_instability",
    "S006": "progressive_mold_wear_dimension_drift",
}
HEALTHY_WINDOWS = (
    ("1003", "OF-2025-0004", "2025-02-10T06:40:00", "flash"),
    ("606", "OF-2025-0007", "2025-02-10T06:40:00", "warpage"),
    ("152", "OF-2025-0001", "2025-02-10T06:40:00", "short_shot"),
    ("152", "OF-2025-0021", "2025-02-12T23:15:00", "short_shot"),
    ("1003", "OF-2025-0031", "2025-02-13T07:44:00", "flash"),
    ("606", "OF-2025-0044", "2025-02-14T15:37:00", "warpage"),
)


def load_cases(path: Path = GROUND_TRUTH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(db_url: str, truth_path: Path = GROUND_TRUTH) -> list[dict[str, Any]]:
    cases = load_cases(truth_path)
    with psycopg2.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, erp_ref FROM machines")
        machine_ids = {str(ref): int(machine_id) for machine_id, ref in cur.fetchall()}

    investigator = DeterministicInvestigator(
        PostgresDiagnosticRepository(db_url),
        minimum_event_cycles=30,
        minimum_quality_checks=1,
        abstain_on_insufficient=True,
    )
    results: list[dict[str, Any]] = []
    for case in cases:
        scenario_id = str(case["scenario_id"])
        machine_ref = str(case["machine_erp_ref"])
        defect = "multiple" if scenario_id == "S005" else str(case["expected_defect"]).split(",", 1)[0].strip()
        result = investigator.investigate(
            machine_id=machine_ids[machine_ref],
            machine_erp_ref=machine_ref,
            production_order_id=str(case["production_order_id"]),
            started_at=case["start_time"],
            ended_at=case["end_time"],
            defect_type=defect,
            incident_id=f"eval-{scenario_id}",
        )
        causes = [hypothesis.cause_code for hypothesis in result.hypotheses]
        evidence_ids = {evidence.id for evidence in result.evidence}
        cited_ids = {evidence_id for hypothesis in result.hypotheses for evidence_id in hypothesis.supporting_evidence_ids}
        expected = EXPECTED_CAUSES[scenario_id]
        results.append({
            "scenario_id": scenario_id,
            "expected_cause": expected,
            "top_2": causes,
            "top_2_hit": expected in causes[:2],
            "evidence_count": len(result.evidence),
            "all_citations_resolve": cited_ids <= evidence_ids,
            "data_quality": result.data_quality,
            "confidence": result.hypotheses[0].confidence if result.hypotheses else 0,
        })
    return results


def evaluate_healthy(db_url: str) -> dict[str, Any]:
    from datetime import datetime, timedelta, timezone

    with psycopg2.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, erp_ref FROM machines")
        machine_ids = {str(ref): int(machine_id) for machine_id, ref in cur.fetchall()}
    investigator = DeterministicInvestigator(
        PostgresDiagnosticRepository(db_url),
        minimum_event_cycles=30,
        minimum_quality_checks=1,
        abstain_on_insufficient=True,
    )
    abstained = 0
    for machine_ref, order_id, start_value, defect in HEALTHY_WINDOWS:
        start = datetime.fromisoformat(start_value).replace(tzinfo=timezone.utc)
        try:
            investigator.investigate(
                machine_id=machine_ids[machine_ref], production_order_id=order_id,
                started_at=start, ended_at=start + timedelta(minutes=30), defect_type=defect,
            )
        except InsufficientDataError:
            abstained += 1
    return {"windows": len(HEALTHY_WINDOWS), "abstained": abstained, "abstention_rate": abstained / len(HEALTHY_WINDOWS)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", default="postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv")
    parser.add_argument("--truth", type=Path, default=GROUND_TRUTH)
    args = parser.parse_args()
    results = evaluate(args.db_url, args.truth)
    healthy = evaluate_healthy(args.db_url)
    report = {"scenarios": results, "top_2_recall": sum(item["top_2_hit"] for item in results) / len(results), "healthy_windows": healthy}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item["top_2_hit"] and item["all_citations_resolve"] for item in results) and healthy["abstention_rate"] >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
