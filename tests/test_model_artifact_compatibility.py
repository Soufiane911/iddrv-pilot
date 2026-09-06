from __future__ import annotations

import json
from pathlib import Path
import warnings

import pandas as pd
import pytest
from sklearn.exceptions import InconsistentVersionWarning

from ml.artifact_contract import ArtifactContractError, load_serialized_artifact, model_path_from_env
from ml.process_drift import load_artifact as load_hdt_artifact
from ml.rebut_risk import load_artifact as load_rebut_artifact


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("artifact_path", "loader"),
    [
        (ROOT / "models/process_drift_hdt_v1.joblib", load_hdt_artifact),
        (ROOT / "models/rebut_risk_v1.joblib", load_rebut_artifact),
    ],
)
def test_published_artifacts_load_without_sklearn_version_warning(artifact_path, loader):
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        artifact = loader(artifact_path)
    assert artifact["model_version"]


def test_loader_rejects_inconsistent_sklearn_warning(monkeypatch, tmp_path):
    import ml.artifact_contract as contracts

    path = tmp_path / "model.joblib"
    path.write_bytes(b"not used")

    def incompatible_load(_path):
        warnings.warn(
            InconsistentVersionWarning(
                estimator_name="IsolationForest",
                current_sklearn_version="1.7.2",
                original_sklearn_version="1.9.0",
            )
        )
        return {}

    monkeypatch.setattr(contracts.joblib, "load", incompatible_load)
    with pytest.raises(ArtifactContractError, match="Incompatible sklearn version"):
        load_serialized_artifact(path)


def test_default_model_paths_are_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROCESS_DRIFT_MODEL_PATH", raising=False)
    path = model_path_from_env("PROCESS_DRIFT_MODEL_PATH", "process_drift_hdt_v1.joblib")
    assert path == ROOT / "models" / "process_drift_hdt_v1.joblib"


def test_published_metadata_records_runtime_and_contract():
    for name in ("process_drift_hdt_v1", "rebut_risk_v1"):
        metadata = json.loads((ROOT / "models" / f"{name}.meta.json").read_text(encoding="utf-8"))
        assert metadata["environment"] == {
            "python": "3.13.9",
            "scikit_learn": "1.7.2",
            "joblib": "1.5.2",
        }
        assert metadata["feature_columns"]
        assert metadata["metrics"]
        assert metadata["time_boundary"]["train_end"]
        assert metadata["time_boundary"]["test_start"]


def test_raw_cycle_loader_does_not_read_evaluation_truth(tmp_path):
    from ml.process_drift import load_cycle_files

    frame = pd.DataFrame({"timestamp": ["2025-01-01T00:00:00Z"], "scrap_flag": [0]})
    frame.to_csv(tmp_path / "machine_cycles_1.csv", index=False)
    (tmp_path / "ground_truth.json").write_text("not valid JSON", encoding="utf-8")

    loaded = load_cycle_files(tmp_path)
    assert len(loaded) == 1
    assert list(loaded.columns) == ["timestamp", "scrap_flag"]
