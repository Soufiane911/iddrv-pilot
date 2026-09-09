"""Integrity-checked packages. Hash pin MUST come from trusted deployment config.

A digest supplied by the same untrusted uploader is not an approval. Joblib is
executable pickle: this loader is not a public upload endpoint or a sandbox.
"""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import platform
import warnings

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import IsolationForest
from .runtime import FEATURES, SENSORS, UNITS, POLICY

SOURCE_SHA256 = 'f70c137b944a04da6c8f1c405c4b217322019e60d3bb1e5d63066947d9a888ad'


def digest(data):
    return sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def environment():
    return dict(python=platform.python_version(), sklearn=sklearn.__version__,
                numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__,
                joblib=joblib.__version__)


def code_hashes():
    root = Path(__file__).parent
    return {p.name: digest(p.read_bytes()) for p in sorted(root.glob('*.py'))}


@dataclass(frozen=True)
class Package:
    runtime_id: str
    contexts: dict
    models: dict
    manifest: dict


def load_package(path, *, expected_manifest_sha256, allow_test_package=False):
    """Load only a privately approved package with an independently pinned hash.

    All hashes, policy, environment and metadata checked BEFORE unpickling bytes.
    Strict dependency versions; incompatibilities/warnings fail explicitly.
    """
    path = Path(path)
    raw = (path / 'manifest.json').read_bytes()
    if digest(raw) != expected_manifest_sha256:
        raise ValueError('summary6 manifest SHA256 mismatch')
    m = json.loads(raw)
    claimed = m.pop('runtime_id')
    if claimed != 'summary6-' + digest(canonical(m)):
        raise ValueError('summary6 runtime identity mismatch')
    if m['code_sha256'] != code_hashes():
        raise ValueError('summary6 runtime code mismatch')
    if m['environment'] != environment():
        raise ValueError(f"summary6 environment mismatch: required {m['environment']}, actual {environment()}")
    if (m['features'] != list(FEATURES) or m['sensors'] != list(SENSORS)
            or m['units'] != UNITS or m['policy'] != POLICY):
        raise ValueError('summary6 feature/policy contract mismatch')
    is_test = m['scientific_status'] == 'TINY_SYNTHETIC_TEST_ONLY'
    if is_test and not allow_test_package:
        raise ValueError('tiny synthetic package is test-only')
    if m['source_sha256'] != SOURCE_SHA256 and not (is_test and allow_test_package):
        raise ValueError('unapproved summary6 source')
    if not is_test and len(m['contexts']) != 6:
        raise ValueError('approved summary6 requires six synthetic contexts')
    contexts = {}
    for r in m['contexts']:
        key = tuple(r['key'])
        if len(key) != 2 or key in contexts:
            raise ValueError('invalid/duplicate context')
        center, scale = np.asarray(r['center']), np.asarray(r['scale'])
        if (center.shape != (8,) or scale.shape != (8,) or
                not np.isfinite(center).all() or not np.isfinite(scale).all()
                or (scale <= 0).any() or not np.isfinite(r['threshold'])):
            raise ValueError('invalid reference/threshold')
        contexts[key] = r
    payload = (path / 'models.joblib').read_bytes()
    if digest(payload) != m['models_sha256']:
        raise ValueError('summary6 models SHA256 mismatch')
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        models = joblib.load(BytesIO(payload))
    if set(models) != set(contexts) or not models:
        raise ValueError('summary6 context/model mismatch')
    for model in models.values():
        if type(model) is not IsolationForest or model.n_features_in_ != 6:
            raise ValueError('summary6 requires standard sklearn six-feature IsolationForest')
    m['runtime_id'] = claimed
    return Package(claimed, contexts, models, m)


def write_package(destination, *, models, contexts, source_sha256, scientific_status, provenance):
    """Internal packaging utility; no training or calibration. Destination must be new."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    joblib.dump(models, destination / 'models.joblib', compress=3)
    m = dict(format='summary6-v1', source_sha256=source_sha256,
             models_sha256=digest((destination / 'models.joblib').read_bytes()),
             code_sha256=code_hashes(), environment=environment(), features=list(FEATURES),
             sensors=list(SENSORS), units=UNITS, policy=POLICY, contexts=contexts,
             scientific_status=scientific_status, provenance=provenance)
    m['runtime_id'] = 'summary6-' + digest(canonical(m))
    raw = canonical(m)
    (destination / 'manifest.json').write_bytes(raw)
    return digest(raw)
