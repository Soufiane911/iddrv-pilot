"""Usage: python scripts/certification/extract_sources.py contract.json --output NEW_DIR."""
import argparse
import json
import os
from pathlib import Path

from sources.collect import SourceError, collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contract', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    try:
        if args.contract.stat().st_size > 65536:
            raise SourceError('contract_limit')
        spec = json.loads(args.contract.read_text())
        output, manifest = collect(spec)
        (args.output / 'records.jsonl').write_bytes(output)
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        for path in args.output.iterdir():
            os.chmod(path, 0o600)
        print(json.dumps({'status': 'ok', 'source_id': manifest['source_id'], 'rows': manifest['rows']}))
    except Exception as exc:
        code = str(exc) if isinstance(exc, SourceError) else 'extraction_failed'
        (args.output / 'error.json').write_text(json.dumps({'status': 'error', 'code': code}) + '\n')
        print(json.dumps({'status': 'error', 'code': code}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
