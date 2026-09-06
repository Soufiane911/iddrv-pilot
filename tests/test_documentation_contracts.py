from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hdt_demo_documents_gateway_and_temporary_outputs():
    document = (ROOT / "ml" / "HDT-demo-script.md").read_text(encoding="utf-8")

    assert "http://localhost:8080/api/health" in document
    assert "http://localhost:" + "8000" not in document
    assert "http://localhost:8080/api/v1/process-drift" in document
    assert "http://localhost:8080/api/v1/incidents/<INCIDENT_ID>/investigations" in document
    assert "http://localhost:8080/api/v1/incidents/<INCIDENT_ID>/feedback" in document
    assert "/tmp/process_drift_hdt_v1.joblib" in document
    assert "/tmp/process_drift_hdt_v1.meta.json" in document
    assert "création de `models/process_drift_hdt_v1.joblib`" not in document


def test_hdt_certification_matches_published_metadata():
    metadata = json.loads(
        (ROOT / "models" / "process_drift_hdt_v1.meta.json").read_text(encoding="utf-8")
    )
    document = (ROOT / "ml" / "HDT-certification-update.md").read_text(encoding="utf-8")
    metrics = metadata["metrics"]

    def percent(key: str) -> str:
        return f"{metrics[key] * 100:.2f}".replace(".", ",") + " %"

    assert metadata["rows"] == {
        "train": 25500,
        "test": 12753,
        "train_instability_events": 601,
        "test_instability_events": 156,
    }
    assert f"**{percent('average_precision')}**" in document
    assert f"**{percent('baseline_prevalence')}**" in document
    assert f"**{metrics['lift_over_prevalence']:.2f}".replace(".", ",") + "×**" in document
    assert f"**{metrics['roc_auc']:.3f}".replace(".", ",") + "**" in document
    assert f"**{percent('precision_instability')}**" in document
    assert f"**{percent('recall_instability')}**" in document
    assert f"**{percent('alert_rate')}**" in document
    assert "259 / 12 753" in document


def test_external_hdt_sources_are_explicitly_immutable_and_not_local_proof():
    document = (ROOT / "ml" / "HDT-certification-update.md").read_text(encoding="utf-8")
    sources = (ROOT / "ml" / "EXTERNAL-SOURCES.md").read_text(encoding="utf-8")

    assert "ne sont pas disponibles dans ce checkout" in document
    assert "feadef7268cb87a16228be254e0e786aa0f55d63" in sources
    assert "source-plasturgie/" in sources
    assert "source-plasturgie/veille-index/journal-veille.md" not in document


def test_readme_separates_product_and_destructive_e2e_tests():
    document = (ROOT / "README.md").read_text(encoding="utf-8")

    assert ".venv/bin/python -m pytest -q --ignore=tests/e2e" in document
    assert ".venv/bin/python tests/e2e/run_tests.py --tier 1,2" in document
    assert re.search(r"E2E\s+préparés sont destructifs", document)
    assert "E2E_DESTRUCTIVE_CLEANUP_CONFIRMATION" in document
