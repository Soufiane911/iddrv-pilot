"""Offline deterministic, allowlisted extraction; no outcomes are read."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

SOURCE = '03953646a5eae466ddbd1e86e7295a0a9670442161b461284cc7c78a396b4e6e'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.summary6 import UNITS


def extract(source):
    raw = Path(source).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE, 'unapproved observations'
    lots = [f'M{m}-R{r}-L15' for m in range(1, 4) for r in range(1, 3)]
    rows = {lot: [] for lot in lots}
    for row in csv.DictReader(io.StringIO(gzip.decompress(raw).decode())):
        if row['lot_id'] in rows:
            rows[row['lot_id']].append({
                'timestamp': row['timestamp'],
                'cycle': {'source_id': 'synthetic-61007', 'machine_erp_ref': row['machine_erp_ref'],
                          'recipe_id': row['recipe_id'], 'lot_id': row['lot_id'],
                          'cycle_counter': int(row['cycle_counter']), 'units': UNITS,
                          'sensors': {k: float(row[k]) for k in UNITS}}})
    target = ROOT / 'data/summary6'
    target.mkdir(exist_ok=True)
    entries = []
    for lot, records in rows.items():
        assert [r['cycle']['cycle_counter'] for r in records] == list(range(400))
        content = ''.join(json.dumps(r, sort_keys=True, separators=(',', ':'))+'\n' for r in records).encode()
        data = gzip.compress(content, mtime=0)
        (target / f'{lot}.jsonl.gz').write_bytes(data)
        entries.append({'lot_id': lot, 'sha256': hashlib.sha256(data).hexdigest(), 'count': 400})
    manifest = {'dataset_id': 'synthetic-61007-l15-v1', 'synthetic': True,
                'source': 'output/hdt-feature-hypotheses-2026-09-07/run01/confirmation/dataset_61007/observations.csv.gz',
                'source_sha256': SOURCE, 'selection': 'M1/M2/M3 x R1/R2, L15, counters 0..399; no outcome selection',
                'lots': entries}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')

if __name__ == '__main__':
    extract(sys.argv[1])
