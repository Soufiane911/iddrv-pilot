"""Installation and generated-data contracts independent of any private files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_training_generator_deterministic_bounded_and_no_overwrite(tmp_path):
    from scripts.generate_training_fixture import generate
    first, second = generate(tmp_path / 'first'), generate(tmp_path / 'second')
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in first.iterdir()} == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in second.iterdir()}
    provenance = json.loads((first / 'provenance.json').read_text())
    assert provenance['production_qualified'] is False
    assert provenance['cycles_per_machine'] == 1200
    with pytest.raises(FileExistsError):
        generate(first)


def test_missing_cycle_files_fail_precisely(tmp_path):
    from ml.process_drift import load_cycle_files
    with pytest.raises(FileNotFoundError, match=r'No machine_cycles_\*\.csv files found'):
        load_cycle_files(tmp_path / 'absent')


def test_missing_observations_readiness_with_loaded_package(tmp_path, monkeypatch):
    from backend.app.services import summary6 as service
    monkeypatch.setenv('HDT_RUNTIME_MODE', 'summary6_replay')
    monkeypatch.setattr(service, 'DATA', tmp_path / 'absent')
    monkeypatch.setattr(service, 'package', lambda: SimpleNamespace(runtime_id=service.PACKAGE_ID))
    state = service.current()
    assert state['readiness'] == 'not_ready'
    assert state['reasons'] == ['summary6_dataset_unavailable']
    assert not state['replay_enabled'] and not state['live_enabled']
    assert not service.DATA.exists()


def test_operator_data_directory_does_not_change_manifest_pin(tmp_path):
    from backend.app.services import summary6 as service
    result = subprocess.run([sys.executable, '-c',
        'from backend.app.services.summary6 import DATA, MANIFEST_SHA; '
        'import json; print(json.dumps([str(DATA), MANIFEST_SHA]))'],
        cwd=ROOT, env=dict(os.environ, SUMMARY6_DATA_DIR=str(tmp_path / 'external')),
        check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [str(tmp_path / 'external'), service.MANIFEST_SHA]


def test_tampered_demo_manifest_rejected(summary6_data):
    from backend.app.services import summary6 as service
    (summary6_data / 'manifest.json').write_text('{}')
    with pytest.raises(service.Unavailable, match='summary6_dataset_unavailable'):
        service.verify_demo_files()


def test_backend_docker_copy_sources_are_public():
    # Validate actual COPY sources in a clean export without invoking Docker/containers.
    dockerfile = (ROOT / 'backend/Dockerfile').read_text()
    for line in dockerfile.splitlines():
        if line.startswith('COPY '):
            for source in line.split()[1:-1]:
                assert source.split('/')[0] not in {'data', 'docs', '.gitignore', 'REPORT_ALIGNMENT.md'}
                assert (ROOT / source).exists(), source
    excluded = set((ROOT / '.dockerignore').read_text().splitlines())
    assert {'data', 'docs', 'REPORT_ALIGNMENT.md', '.gitignore', '.env', '.env.*'} <= excluded
    override = (ROOT / 'deploy/compose.local-private.yml').read_text()
    assert override.count('read_only: true') == 2
    assert override.count('create_host_path: false') == 2
