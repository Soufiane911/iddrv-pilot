"""Read-only synthetic replay. Never uses DB history, outcomes or incident writers."""
import gzip
import hashlib
import json
import os
from pathlib import Path

from ml.runtime_mode import runtime_mode
from ml.summary6 import load_package, score_cycles

PACKAGE_ID = 'summary6-0c8b4c15cd4df33784468dfcd2057b52261122a8c90dbb0b1ba4a117b2870702'
DATA = Path(__file__).resolve().parents[3] / 'data' / 'summary6'
MANIFEST_SHA = 'f0d95e3b88ab5c3cefe50483acac62fa6f674f8e85a9c60b721c0100c06a018b'


class Unavailable(Exception):
    pass


def package():
    # Reverify on each request: replacement/tampering cannot be hidden by a cache.
    try:
        loaded = load_package(os.environ['SUMMARY6_PACKAGE_DIR'],
                              expected_manifest_sha256=os.environ['SUMMARY6_MANIFEST_SHA256'])
        if loaded.runtime_id != PACKAGE_ID:
            raise ValueError('unselected_package')
        return loaded
    except Exception:
        raise Unavailable('summary6_package_unavailable') from None


def catalog():
    try:
        raw = (DATA / 'manifest.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
            raise ValueError()
        return json.loads(raw)
    except Exception:
        raise Unavailable('summary6_dataset_unavailable') from None


def current():
    loaded = None
    reasons = []
    try:
        loaded = package().runtime_id
        catalog()
    except Unavailable as exc:
        reasons.append(str(exc))
    mode = runtime_mode()
    if mode != 'summary6_replay':
        reasons.append('summary6_profile_not_enabled')
    return dict(selected_package_id=PACKAGE_ID, loaded_package_id=loaded,
                readiness='ready' if not reasons else 'not_ready',
                replay_enabled=not reasons, live_enabled=False,
                reasons=reasons, active_mode=mode)


def replay(source, loaded):
    manifest = catalog()
    entry = next((x for x in manifest['lots'] if x['lot_id'] == source.lot_id), None)
    if source.dataset_id != manifest['dataset_id'] or entry is None:
        raise ValueError('unknown_demo_dataset_or_lot')
    try:
        # Filename comes from the pinned manifest, not client input.
        data = (DATA / (entry['lot_id'] + '.jsonl.gz')).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError()
        records = []
        # Only the requested prefix is decoded; no later sensors enter inference.
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            for _ in range(source.through_cycle + 1):
                records.append(json.loads(stream.readline()))
        cycles = [r['cycle'] for r in records]
        results = score_cycles(cycles, package=loaded)
    except Exception:
        raise Unavailable('summary6_replay_unavailable') from None
    return dict(schema_version=1, package_id=loaded.runtime_id,
                manifest_sha256=os.environ['SUMMARY6_MANIFEST_SHA256'],
                active_mode=runtime_mode(), execution_mode='replay', live_enabled=False,
                provenance={'synthetic': True, 'dataset_id': manifest['dataset_id'],
                            'source_sha256': manifest['source_sha256'], 'selection_manifest_sha256': MANIFEST_SHA},
                context={k: cycles[0][k] for k in ('source_id', 'machine_erp_ref', 'recipe_id', 'lot_id', 'units')},
                through_cycle=source.through_cycle, evaluated_through=records[-1]['timestamp'],
                input_count=len(cycles), latest=results[-1], series=results, signals=[])
