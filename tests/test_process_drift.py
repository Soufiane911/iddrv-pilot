import json
import importlib.metadata
import platform
from pathlib import Path

import pandas as pd
import pytest

from ml.process_drift import (
    ANOMALY_FEATURES,
    FEATURE_COLUMNS,
    HORIZON_CYCLES,
    SOURCE_OUTCOME_COLUMN,
    TARGET_COLUMN,
    load_artifact,
    load_cycle_files,
    prepare_frame,
    predict,
    save_artifact,
    temporal_split,
    train,
    prepare_inference_frame,
)


from scripts.generate_training_fixture import CYCLES_PER_MACHINE, MACHINES


def test_hdt_contract_is_future_and_does_not_use_current_quality_columns():
    assert TARGET_COLUMN == "instability_next_20_cycles"
    assert SOURCE_OUTCOME_COLUMN not in FEATURE_COLUMNS
    assert "quality_flag" not in FEATURE_COLUMNS
    assert "defect_type" not in FEATURE_COLUMNS
    assert "production_order_id" not in FEATURE_COLUMNS
    assert "barrel_temp_zone2_c_volatility_20" in FEATURE_COLUMNS
    assert HORIZON_CYCLES == 20


def test_load_cycle_files_returns_raw_cycles_without_derived_columns(training_data):
    frame = load_cycle_files(training_data)

    assert len(frame) == CYCLES_PER_MACHINE * len(MACHINES)
    assert TARGET_COLUMN not in frame.columns
    assert not set(ANOMALY_FEATURES).intersection(frame.columns)


def test_prepare_frame_rejects_already_prepared_data(training_data):
    frame = load_cycle_files(training_data)
    prepared = prepare_frame(frame)

    with pytest.raises(ValueError, match="already prepared"):
        prepare_frame(prepared)


def test_prepare_frame_drops_only_terminal_horizon_per_machine(training_data):
    frame = load_cycle_files(training_data)

    prepared = prepare_frame(frame)

    assert len(prepared) == (CYCLES_PER_MACHINE - HORIZON_CYCLES) * len(MACHINES)
    assert frame["machine_erp_ref"].nunique() == 3
    assert len(frame) - len(prepared) == HORIZON_CYCLES * 3


def test_temporal_split_is_strict_inside_each_machine(training_data):
    prepared = prepare_frame(load_cycle_files(training_data))

    train_frame, test_frame = temporal_split(prepared)

    for machine in prepared["machine_erp_ref"].unique():
        train_machine = train_frame[train_frame["machine_erp_ref"] == machine]
        test_machine = test_frame[test_frame["machine_erp_ref"] == machine]
        assert not train_machine.empty
        assert not test_machine.empty
        assert train_machine["timestamp"].max() < test_machine["timestamp"].min()


def test_hdt_training_is_temporal_reproducible_and_packaged(tmp_path, training_data):
    frame = load_cycle_files(training_data)
    result = train(frame)

    assert result.train_rows > 1000
    assert result.test_rows > 1000
    assert result.train_events > 0
    assert result.test_events > 0
    assert result.train_end != result.test_start
    assert 0 <= result.metrics["average_precision"] <= 1
    assert 0 <= result.metrics["roc_auc"] <= 1
    assert 0 <= result.metrics["precision_instability"] <= 1
    assert 0 <= result.metrics["recall_instability"] <= 1
    assert result.metrics["horizon_cycles"] == 20
    assert result.metrics["lift_over_prevalence"] >= 1

    artifact_path = tmp_path / "process_drift.joblib"
    metadata_path = tmp_path / "process_drift.meta.json"
    save_artifact(result, artifact_path, metadata_path)
    artifact = load_artifact(artifact_path)
    sample = prepare_inference_frame(frame.head(3))
    predictions = predict(artifact, sample)

    assert list(predictions.columns) == [
        "anomaly_score",
        "predicted_instability_next_20_cycles",
        "threshold",
        "horizon_cycles",
        "model_version",
    ]
    assert len(predictions) == 3
    assert predictions["anomaly_score"].ge(0).all()
    assert predictions["horizon_cycles"].eq(20).all()
    assert predictions["model_version"].eq("hdt-process-drift-iforest-v1").all()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["contract"]["ground_truth_used"] is False
    assert metadata["contract"]["algorithm"] == "machine_contextualized_isolation_forest"
    assert set(metadata["time_boundary"]["per_machine"]) == {"152", "606", "1003"}
    assert all(
        boundaries["train_end"] < boundaries["test_start"]
        for boundaries in metadata["time_boundary"]["per_machine"].values()
    )
    assert metadata["environment"] == {
        "python": platform.python_version(),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "joblib": importlib.metadata.version("joblib"),
    }


def test_hdt_runtime_features_do_not_require_future_labels(training_data):
    frame = load_cycle_files(training_data).drop(columns=[SOURCE_OUTCOME_COLUMN])
    runtime = prepare_inference_frame(frame.head(25))
    assert TARGET_COLUMN not in runtime.columns
    assert SOURCE_OUTCOME_COLUMN not in runtime.columns
    assert "cooling_time_s_volatility_20" in runtime.columns


def test_hdt_prediction_rejects_incomplete_feature_contract(training_data):
    result = train(load_cycle_files(training_data))
    try:
        predict(result.artifact, pd.DataFrame({"cycle_time_s": [1.0]}))
    except ValueError as exc:
        assert "missing columns" in str(exc)
    else:
        raise AssertionError("prediction must reject an incomplete feature contract")
