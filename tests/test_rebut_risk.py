from pathlib import Path

import pandas as pd

from ml.rebut_risk import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    load_artifact,
    load_cycle_files,
    predict,
    save_artifact,
    train,
)


DATA_DIR = Path("data/scenarios/industrial_demo")


def test_training_contract_uses_process_features_only():
    assert TARGET_COLUMN == "scrap_flag"
    assert TARGET_COLUMN not in FEATURE_COLUMNS
    assert "quality_flag" not in FEATURE_COLUMNS
    assert "defect_type" not in FEATURE_COLUMNS
    assert "part_quality_status" not in FEATURE_COLUMNS


def test_rebut_risk_training_is_temporal_and_reproducible(tmp_path):
    frame = load_cycle_files(DATA_DIR)
    result = train(frame)

    assert result.train_rows == 25542
    assert result.test_rows == 12771
    assert result.train_scraps == 590
    assert result.test_scraps == 207
    assert result.train_end < result.test_start
    assert 0 <= result.metrics["average_precision"] <= 1
    assert 0 <= result.metrics["roc_auc"] <= 1
    assert 0 <= result.metrics["precision_scrap"] <= 1
    assert 0 <= result.metrics["recall_scrap"] <= 1

    artifact_path = tmp_path / "rebut_risk.joblib"
    metadata_path = tmp_path / "rebut_risk.meta.json"
    save_artifact(result, artifact_path, metadata_path)
    artifact = load_artifact(artifact_path)
    sample = frame.head(3)
    predictions = predict(artifact, sample)

    assert list(predictions.columns) == [
        "risk_probability",
        "predicted_scrap",
        "threshold",
        "model_version",
    ]
    assert len(predictions) == 3
    assert predictions["risk_probability"].between(0, 1).all()
    assert predictions["model_version"].eq("rebut-risk-logistic-v1").all()
    assert metadata_path.read_text(encoding="utf-8").find("chronological_2_3_train_1_3_test") >= 0


def test_prediction_rejects_missing_feature():
    frame = load_cycle_files(DATA_DIR)
    result = train(frame)
    try:
        predict(result.artifact, pd.DataFrame({"cycle_time_s": [1.0]}))
    except ValueError as exc:
        assert "missing columns" in str(exc)
    else:
        raise AssertionError("prediction must reject an incomplete feature contract")
