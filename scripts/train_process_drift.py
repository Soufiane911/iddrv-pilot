#!/usr/bin/env python3
"""Train and package the HDT process-drift model without evaluation truth files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.process_drift import load_cycle_files, save_artifact, train


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the IDDRV HDT process-drift model")
    parser.add_argument("--data-dir", type=Path, default=Path("data/scenarios/industrial_demo"))
    parser.add_argument("--artifact", type=Path, default=Path("models/process_drift_hdt_v1.joblib"))
    parser.add_argument("--metadata", type=Path, default=Path("models/process_drift_hdt_v1.meta.json"))
    args = parser.parse_args()

    frame = load_cycle_files(args.data_dir)
    result = train(frame)
    save_artifact(result, args.artifact, args.metadata)
    print(json.dumps({
        "model_version": result.artifact["model_version"],
        "artifact": str(args.artifact),
        "metadata": str(args.metadata),
        "train_rows": result.train_rows,
        "test_rows": result.test_rows,
        "train_drift_events": result.train_events,
        "test_drift_events": result.test_events,
        "metrics": result.metrics,
        "train_end": result.train_end,
        "test_start": result.test_start,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
