#!/usr/bin/env python3
"""Train and publish the HDT process-drift artifact.

The command is deliberately conservative: published model files are never
replaced accidentally. Use ``--force`` only when intentionally regenerating an
artifact, preferably with output paths outside ``models/`` first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.process_drift import load_cycle_files, save_artifact, train  # noqa: E402


DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "scenarios" / "industrial_demo"
DEFAULT_ARTIFACT = PROJECT_ROOT / "models" / "process_drift_hdt_v1.joblib"
DEFAULT_METADATA = PROJECT_ROOT / "models" / "process_drift_hdt_v1.meta.json"


def _path_argument(value: str) -> Path:
    return Path(value).expanduser()


def _refuse_existing(paths: tuple[Path, ...], force: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not force:
        joined = ", ".join(existing)
        raise SystemExit(f"Refusing to overwrite existing output(s): {joined}; use --force")


def _validate_metadata_path(artifact: Path, metadata: Path) -> None:
    expected = artifact.with_suffix(".meta.json")
    if metadata.absolute() != expected.absolute():
        raise SystemExit(
            f"Metadata path must be the artifact sidecar ({expected}); got {metadata}"
        )


def _report(result: Any, raw_rows: int, data_dir: Path, artifact: Path, metadata: Path) -> dict[str, Any]:
    return {
        "model_version": result.artifact["model_version"],
        "paths": {
            "data_dir": str(data_dir),
            "artifact": str(artifact),
            "metadata": str(metadata),
        },
        "volumes": {
            "raw": raw_rows,
            "prepared": result.train_rows + result.test_rows,
            "train": result.train_rows,
            "test": result.test_rows,
        },
        "events": {
            "train_instability": result.train_events,
            "test_instability": result.test_events,
        },
        "metrics": result.metrics,
        "time_boundary": {
            "train_end": result.train_end,
            "test_start": result.test_start,
            "per_machine": result.per_machine_boundaries,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=_path_argument, default=DEFAULT_DATA_DIR)
    parser.add_argument("--artifact", type=_path_argument, default=DEFAULT_ARTIFACT)
    parser.add_argument("--metadata", type=_path_argument, default=DEFAULT_METADATA)
    parser.add_argument("--force", action="store_true", help="allow replacing existing outputs")
    args = parser.parse_args(argv)

    _validate_metadata_path(args.artifact, args.metadata)
    _refuse_existing((args.artifact, args.metadata), args.force)
    raw = load_cycle_files(args.data_dir)
    result = train(raw)
    save_artifact(result, args.artifact, args.metadata)
    print(json.dumps(_report(result, len(raw), args.data_dir, args.artifact, args.metadata), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
