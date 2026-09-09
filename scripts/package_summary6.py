#!/usr/bin/env python3
"""Package ONLY the approved first export61007/seed42, never search for a winner."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib
from ml.summary6.registry import SOURCE_SHA256, digest, write_package, load_package
from ml.summary6.runtime import FEATURES

APPROVED = Path('/Users/soufianehamzaoui/Desktop/EPSI/ProjetSeptembre/output/hdt-feature-hypotheses-2026-09-07/run01')


def package(destination):
    source = APPROVED / 'confirmation/candidate_61007.joblib'
    payload = source.read_bytes()
    if digest(payload) != SOURCE_SHA256:
        raise ValueError('approved source SHA256 mismatch; refusing deserialization')
    provenance = json.loads((APPROVED / 'provenance.json').read_text())
    for original, expected in provenance['source_sha256'].items():
        frozen = APPROVED / 'source_snapshot' / Path(original).name
        if digest(frozen.read_bytes()) != expected:
            raise ValueError(f'frozen source hash mismatch: {frozen}')
    # Warnings, including sklearn InconsistentVersionWarning, are fatal.
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        a = joblib.load(BytesIO(payload))
    if (a['representation'] != 'summary6' or a['random_state'] != 42
            or a['features'] != list(FEATURES) or a['budget'] != .0025
            or len(a['models']) != 6):
        raise ValueError('approved export contract mismatch')
    contexts = [dict(key=list(k), center=a['reference'][k][0].tolist(),
                     scale=a['reference'][k][1].tolist(), threshold=float(a['thresholds'][k]))
                for k in sorted(a['models'])]
    pin = write_package(destination, models=a['models'], contexts=contexts,
                        source_sha256=SOURCE_SHA256,
                        scientific_status='EXPERIMENTAL_SYNTHETIC_CONFIRMATION_FAILED_NOT_FACTORY_VALIDATED',
                        provenance=dict(frozen=provenance, selection_sha256=a['selection_sha256'],
                                        export=61007, random_state=42,
                                        selection='deterministic first export, not best seed',
                                        historical_model_unchanged=True))
    loaded = load_package(destination, expected_manifest_sha256=pin)
    print(json.dumps(dict(path=str(destination), manifest_sha256=pin,
                          runtime_id=loaded.runtime_id,
                          models_sha256=loaded.manifest['models_sha256']), indent=2))
    return pin


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path)
    package(parser.parse_args().destination)
