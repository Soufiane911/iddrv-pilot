#!/usr/bin/env python3
"""Build a local candidate, never replace the served model. No deployment."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from ml.artifact_contract import runtime_environment, validate_environment
from ml.process_drift import (
    RAW_NUMERIC_FEATURES, build_pipeline, load_artifact, load_cycle_files, predict,
    prepare_inference_frame, save_artifact, train,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_files(directory: Path, files: dict[str, str], *, dataset: bool = False) -> None:
    """Validate the complete file contract before I/O; integrity is not authenticity."""
    required = {'process_drift_hdt_v1.joblib', 'process_drift_hdt_v1.meta.json'}
    if not isinstance(files, dict) or not files or (not dataset and set(files) != required):
        raise ValueError('Package integrity failed: incomplete or unknown file entries')
    for name, expected in files.items():
        if (not isinstance(name, str) or Path(name).name != name
                or (dataset and not (name.startswith('machine_cycles_') and name.endswith('.csv')))
                or not isinstance(expected, str) or re.fullmatch(r'[0-9a-fA-F]{64}', expected) is None):
            raise ValueError(f'Package integrity failed: invalid entry {name}')
    for name, expected in files.items():
        if sha256(directory / name) != expected.lower():
            raise ValueError(f'Package integrity failed: {name}')


def package(data_dir: Path, output: Path) -> dict:
    environment = runtime_environment()
    validate_environment({'environment': environment})
    # Exclusive directory creation also refuses any overwrite of models/.
    if output.resolve().is_relative_to((ROOT / 'models').resolve()):
        raise ValueError('Candidates must be outside models/')
    if output.exists():
        raise FileExistsError(output)
    inputs = {p.name: sha256(p) for p in sorted(data_dir.glob('machine_cycles_*.csv'))}
    raw = load_cycle_files(data_dir)
    required = list(RAW_NUMERIC_FEATURES) + ['timestamp', 'machine_erp_ref', 'scrap_flag']
    raw[required]  # fail explicitly on missing schema columns
    if raw.empty or raw[['timestamp', 'machine_erp_ref', 'scrap_flag']].isna().any().any():
        raise ValueError('Dataset empty or incomplete')
    if not raw['scrap_flag'].isin([0, 1]).all():
        raise ValueError('Dataset labels must be exactly 0/1')
    numeric = raw[list(RAW_NUMERIC_FEATURES)].to_numpy(dtype=float)
    if np.isinf(numeric).any() or raw[list(RAW_NUMERIC_FEATURES)].isna().all().any():
        raise ValueError('Dataset numeric values contain infinity or an entirely missing feature')
    raw['timestamp'] = pd.to_datetime(raw['timestamp'], utc=True, errors='raise')
    if raw['timestamp'].isna().any():
        raise ValueError('Dataset timestamps contain NaT')
    if raw.duplicated(['machine_erp_ref', 'timestamp']).any():
        raise ValueError('Duplicate machine/timestamp')
    result = train(raw)  # existing preparation, per-machine split and evaluation
    if not all(np.isfinite(value) for value in result.metrics.values()):
        raise ValueError('Non-finite evaluation metrics')
    if result.metrics['lift_over_prevalence'] < 1:
        raise ValueError('Candidate fails offline proxy gate: lift < 1')
    verify_files(data_dir, inputs, dataset=True)
    output.mkdir(parents=True, exist_ok=False)
    artifact = output / 'process_drift_hdt_v1.joblib'
    metadata = artifact.with_suffix('.meta.json')
    save_artifact(result, artifact, metadata)
    files = {p.name: sha256(p) for p in (artifact, metadata)}
    verify_files(output, files)  # before deserializing our own newly trained file
    loaded = load_artifact(artifact)
    smoke = prepare_inference_frame(raw.groupby('machine_erp_ref', sort=False).tail(64))
    expected = predict(result.artifact, smoke)
    observed = predict(loaded, smoke)
    pd.testing.assert_frame_equal(expected, observed, check_exact=True)
    if not np.isfinite(observed['anomaly_score']).all():
        raise ValueError('Non-finite inference output')
    manifest = {
        'schema_version': 1, 'kind': 'local-candidate-not-deployed',
        'model_version': loaded['model_version'], 'files': files,
        'dataset': {'files': inputs, 'raw_rows': len(raw), 'ground_truth_used': False,
                    'missing_values': {key: int(value) for key, value in raw[required].isna().sum().items()}},
        'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': {name: sha256(ROOT / name) for name in
                          ('ml/process_drift.py', 'ml/artifact_contract.py', 'scripts/package_process_drift.py')},
        'environment': {**environment, 'numpy': np.__version__, 'pandas': pd.__version__},
        'config': {'seed': 42, 'train_fraction': 2 / 3,
                   'estimator': build_pipeline().named_steps['isolation_forest'].get_params(),
                   'training_contract': loaded['training_contract']},
        'metrics': result.metrics, 'validation': {'minimum_lift': 1, 'smoke_rows': len(smoke),
                                                'roundtrip_exact': True},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new candidate directory')
    print(json.dumps(package(args.data_dir, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
