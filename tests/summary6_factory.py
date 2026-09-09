"""Synthetic filesystem fixture: no private manifest, datasets or models are read."""
import gzip
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone

from ml.summary6 import UNITS


def demo_catalog(folder):
    folder.mkdir()
    lots = []
    for machine in ('M1', 'M2', 'M3'):
        for recipe in ('R1', 'R2'):
            lot = f'{machine}-{recipe}-L15'
            rows = []
            for i in range(400):
                rows.append(json.dumps({
                    'timestamp': (datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)).isoformat(),
                    'cycle': {
                        'source_id': 'synthetic-61007', 'machine_erp_ref': machine,
                        'recipe_id': recipe, 'lot_id': lot, 'cycle_counter': i,
                        'units': UNITS,
                        'sensors': {name: 10.0 * (j + 1) + math.sin(i / 7 + j) for j, name in enumerate(UNITS)},
                    },
                }, sort_keys=True))
            raw = gzip.compress(('\n'.join(rows) + '\n').encode(), mtime=0)
            (folder / f'{lot}.jsonl.gz').write_bytes(raw)
            lots.append({'lot_id': lot, 'machine_erp_ref': machine, 'recipe_id': recipe,
                         'cycle_count': 400, 'sha256': hashlib.sha256(raw).hexdigest()})
    raw = json.dumps({'dataset_id': 'synthetic-61007-l15-v1', 'synthetic': True,
                      'source_sha256': 'generated-software-test-only', 'lots': lots}, sort_keys=True).encode()
    (folder / 'manifest.json').write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
