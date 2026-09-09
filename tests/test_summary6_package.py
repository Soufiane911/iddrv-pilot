"""Packaging fail-closed checks; no external pickles accepted by the exporter."""
import json
from pathlib import Path
import runpy

import pytest

from ml.summary6.registry import canonical, digest, load_package
from test_summary6_runtime import tiny  # shared explicitly synthetic fixture


def test_export_source_hash_before_pickle(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/package_summary6.py'))
    exporter = namespace['package']
    exporter.__globals__['APPROVED'] = tmp_path
    (tmp_path / 'confirmation').mkdir()
    (tmp_path / 'confirmation/candidate_61007.joblib').write_bytes(b'not-approved-pickle')
    def forbidden(*args, **kwargs):
        raise AssertionError('source hash must be checked first')
    monkeypatch.setattr(namespace['joblib'], 'load', forbidden)
    with pytest.raises(ValueError, match='source SHA256'):
        exporter(tmp_path / 'new-package')


@pytest.mark.parametrize('change,message', [('environment', 'environment mismatch'),
                                           ('code_sha256', 'code mismatch'),
                                           ('policy', 'contract mismatch')])
def test_metadata_checked_before_pickle(tiny, monkeypatch, change, message):
    _, path, _ = tiny
    import ml.summary6.registry as registry
    m = json.loads((path / 'manifest.json').read_text())
    m.pop('runtime_id')
    m[change] = {}
    m['runtime_id'] = 'summary6-' + digest(canonical(m))
    raw = canonical(m)
    (path / 'manifest.json').write_bytes(raw)
    def forbidden(*args, **kwargs):
        raise AssertionError('metadata must be checked before pickle')
    monkeypatch.setattr(registry.joblib, 'load', forbidden)
    with pytest.raises(ValueError, match=message):
        load_package(path, expected_manifest_sha256=digest(raw), allow_test_package=True)


def test_tiny_not_loadable_as_production(tiny):
    _, path, pin = tiny
    with pytest.raises(ValueError, match='test-only'):
        load_package(path, expected_manifest_sha256=pin)
