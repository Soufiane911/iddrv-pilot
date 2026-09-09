from pathlib import Path
import json

import pytest

from scripts import package_process_drift as delivery

from scripts.package_process_drift import ROOT, package, sha256, verify_files


def test_served_manifest_integrity_and_contract():
    manifest = json.loads((ROOT / 'models/process_drift_hdt_v1.manifest.json').read_text())
    verify_files(ROOT / 'models', manifest['files'])
    from ml.process_drift import load_artifact
    artifact = load_artifact(ROOT / 'models/process_drift_hdt_v1.joblib')
    assert artifact['model_version'] == manifest['model_version']


def test_integrity_rejects_tampering_before_loading(tmp_path):
    path = tmp_path / 'process_drift_hdt_v1.joblib'
    path.write_bytes(b'not deserialized')
    metadata = tmp_path / 'process_drift_hdt_v1.meta.json'
    metadata.write_text('{}')
    hashes = {p.name: sha256(p) for p in (path, metadata)}
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        verify_files(tmp_path, hashes)
    with pytest.raises(ValueError, match='integrity'):
        verify_files(tmp_path, {'../outside': 'invalid'})


@pytest.mark.parametrize('files', [
    {},
    {'process_drift_hdt_v1.meta.json': 'a' * 64},
    {'process_drift_hdt_v1.joblib': 'a' * 64},
    {'process_drift_hdt_v1.joblib': 'a' * 64,
     'process_drift_hdt_v1.meta.json': 'invalid'},
])
def test_invalid_manifest_rejected_before_deserialization(tmp_path, monkeypatch, files):
    from unittest.mock import Mock
    loader = Mock(side_effect=AssertionError('Must not deserialize'))
    monkeypatch.setattr(delivery, 'load_artifact', loader)
    # Contract validation must even precede attempts to read the listed files.
    monkeypatch.setattr(delivery, 'sha256', Mock(side_effect=AssertionError('Must not read')))
    with pytest.raises(ValueError, match='integrity'):
        verify_files(tmp_path, files)
        delivery.load_artifact(tmp_path / 'process_drift_hdt_v1.joblib')
    loader.assert_not_called()


def test_dataset_integrity_allows_variable_csv_names(tmp_path):
    files = {}
    for name in ('machine_cycles_custom.csv', 'machine_cycles_other.csv'):
        path = tmp_path / name
        path.write_text('sample')
        files[name] = sha256(path)
    verify_files(tmp_path, files, dataset=True)


@pytest.mark.parametrize('timestamps, message', [
    (['2025-01-01T00:00:00+00:00', '2025-01-01T01:00:00+01:00'], 'Duplicate'),
    (['NaT', 'NaT'], 'NaT'),
])
def test_invalid_timestamps_rejected_before_training(tmp_path, monkeypatch, timestamps, message):
    from unittest.mock import Mock
    raw = delivery.load_cycle_files(ROOT / 'data/scenarios/industrial_demo').iloc[:2].copy()
    raw['machine_erp_ref'] = 'same-machine'
    raw['timestamp'] = timestamps
    monkeypatch.setattr(delivery, 'load_cycle_files', lambda _: raw)
    trainer = Mock(side_effect=AssertionError('Must not train'))
    monkeypatch.setattr(delivery, 'train', trainer)
    with pytest.raises(ValueError, match=message):
        package(tmp_path, tmp_path / 'candidate')
    trainer.assert_not_called()
    assert not (tmp_path / 'candidate').exists()


def test_package_roundtrip_reproducible_and_no_overwrite(tmp_path):
    dataset = ROOT / 'data/scenarios/industrial_demo'
    first = package(dataset, tmp_path / 'first')
    second = package(dataset, tmp_path / 'second')
    assert first == second
    assert first['validation']['roundtrip_exact']
    assert first['validation']['smoke_rows'] > 0
    with pytest.raises(FileExistsError):
        package(dataset, tmp_path / 'first')
    with pytest.raises(ValueError, match='outside models'):
        package(dataset, ROOT / 'models/candidate')
