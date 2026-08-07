from pathlib import Path

import pandas as pd

from ml.process_drift import (
    FEATURE_COLUMNS,
    HORIZON_CYCLES,
    SOURCE_OUTCOME_COLUMN,
    TARGET_COLUMN,
    load_artifact,
    load_cycle_files,
    predict,
    save_artifact,
    train,
    prepare_inference_frame,
)


DATA_DIR = Path("data/scenarios/industrial_demo")


def test_hdt_contract_is_future_and_does_not_use_current_quality_columns():
    assert TARGET_COLUMN == "instability_next_20_cycles"
    assert SOURCE_OUTCOME_COLUMN not in FEATURE_COLUMNS
    assert "quality_flag" not in FEATURE_COLUMNS
    assert "defect_type" not in FEATURE_COLUMNS
    assert "production_order_id" not in FEATURE_COLUMNS
    assert "barrel_temp_zone2_c_volatility_20" in FEATURE_COLUMNS
    assert HORIZON_CYCLES == 20


def test_hdt_training_is_temporal_reproducible_and_packaged(tmp_path):
    frame = load_cycle_files(DATA_DIR)
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
    sample = frame.head(3)
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
    metadata = metadata_path.read_text(encoding="utf-8")
    assert "ground_truth_used" in metadata
    assert "machine_contextualized_isolation_forest" in metadata


def test_hdt_runtime_features_do_not_require_future_labels():
    frame = load_cycle_files(DATA_DIR).drop(columns=[TARGET_COLUMN, SOURCE_OUTCOME_COLUMN])
    runtime = prepare_inference_frame(frame.head(25))
    assert TARGET_COLUMN not in runtime.columns
    assert SOURCE_OUTCOME_COLUMN not in runtime.columns
    assert "cooling_time_s_volatility_20" in runtime.columns


def test_hdt_prediction_rejects_incomplete_feature_contract():
    frame = load_cycle_files(DATA_DIR)
    result = train(frame)
    try:
        predict(result.artifact, pd.DataFrame({"cycle_time_s": [1.0]}))
    except ValueError as exc:
        assert "missing columns" in str(exc)
    else:
        raise AssertionError("prediction must reject an incomplete feature contract")
