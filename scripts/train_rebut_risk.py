#!/usr/bin/env python3
"""Train and package the IDDRV scrap-risk baseline without using evaluation truth files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Support both `python scripts/train_rebut_risk.py` and `python -m ...`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.rebut_risk import load_cycle_files, save_artifact, train


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the IDDRV scrap-risk model")
    parser.add_argument("--data-dir", type=Path, default=Path("data/scenarios/industrial_demo"))
    parser.add_argument("--artifact", type=Path, default=Path("models/rebut_risk_v1.joblib"))
    parser.add_argument("--metadata", type=Path, default=Path("models/rebut_risk_v1.meta.json"))
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 < args.threshold < 1:
        parser.error("--threshold must be between 0 and 1")

    frame = load_cycle_files(args.data_dir)
    result = train(frame, threshold=args.threshold)
    save_artifact(result, args.artifact, args.metadata)
    print(json.dumps({
        "model_version": result.artifact["model_version"],
        "artifact": str(args.artifact),
        "metadata": str(args.metadata),
        "train_rows": result.train_rows,
        "test_rows": result.test_rows,
        "train_scraps": result.train_scraps,
        "test_scraps": result.test_scraps,
        "metrics": result.metrics,
        "train_end": result.train_end,
        "test_start": result.test_start,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
