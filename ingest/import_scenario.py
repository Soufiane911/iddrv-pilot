"""Command-line entry point for importing the bundled industrial scenario.

This thin wrapper keeps the documented module command stable while delegating
all parsing, hashing, reconciliation and idempotency to ``ingest_pipeline``.
The evaluation-only ``ground_truth.json`` file is never opened by this module.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .ingest_pipeline import ingest_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="scenario directory to import")
    parser.add_argument("--site-id", type=int, required=True, help="target site database identifier")
    args = parser.parse_args(argv)
    if args.site_id <= 0:
        parser.error("--site-id must be a positive integer")

    ingest_scenario(str(args.directory), site_id=args.site_id)
    print(f"Scenario imported: {args.directory} (site {args.site_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
