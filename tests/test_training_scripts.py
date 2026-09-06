from __future__ import annotations

import pytest

from scripts import train_process_drift, train_rebut_risk


@pytest.mark.parametrize("entrypoint", [train_process_drift, train_rebut_risk])
def test_training_entrypoint_refuses_accidental_overwrite(tmp_path, entrypoint):
    artifact = tmp_path / "model.joblib"
    metadata = tmp_path / "model.meta.json"
    artifact.write_bytes(b"existing")
    metadata.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="--force"):
        entrypoint.main([
            "--data-dir", str(tmp_path / "missing-data"),
            "--artifact", str(artifact),
            "--metadata", str(metadata),
        ])

    assert artifact.read_bytes() == b"existing"
    assert metadata.read_text(encoding="utf-8") == "{}"


@pytest.mark.parametrize("entrypoint", [train_process_drift, train_rebut_risk])
def test_training_entrypoint_requires_metadata_sidecar(tmp_path, entrypoint):
    artifact = tmp_path / "model.joblib"
    metadata = tmp_path / "different.meta.json"

    with pytest.raises(SystemExit, match="Metadata path must be the artifact sidecar"):
        entrypoint.main([
            "--data-dir", str(tmp_path / "missing-data"),
            "--artifact", str(artifact),
            "--metadata", str(metadata),
        ])

    assert not artifact.exists()
    assert not metadata.exists()
