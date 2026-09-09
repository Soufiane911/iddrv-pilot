#!/usr/bin/env python3
"""Bounded local monitoring sandbox; never contacts a deployed stack.

Real DriftMonitor computations on synthetic scores, local-file-test notification
channel. JSON/Prometheus files are evidence, not production notifications.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.monitoring import DriftMonitor  # noqa: E402

CHANNEL = "local-file-test"


def evaluate(snapshot):
    """Indicative sandbox thresholds, not validated production/model policy."""
    if snapshot["recent_window"] < 100:
        return ["insufficient_observations"]
    alerts = []
    if snapshot["psi"] > 0.25:
        alerts.append("score_distribution_shift")
    if snapshot["alert_rate"] > 0.20:
        alerts.append("high_alert_rate")
    return alerts


def run(output: Path):
    # Refuse reuse: never overwrite an earlier run or any existing local data.
    output.mkdir(parents=True, exist_ok=False)
    reference = [i / 1000 for i in range(1000)]
    monitor = DriftMonitor(reference, window=1000)
    active = set()
    events = []
    for phase, scores in (
        ("baseline", reference),
        ("injected_shift", [2.0] * 1000),
        ("recovery", reference),
    ):
        for score in scores:
            monitor.observe(score, threshold=0.98)
        snapshot = monitor.snapshot()
        current = set(evaluate(snapshot))
        for rule in sorted(current - active):
            events.append({"phase": phase, "rule": rule, "state": "firing", "channel": CHANNEL})
        for rule in sorted(active - current):
            events.append({"phase": phase, "rule": rule, "state": "resolved", "channel": CHANNEL})
        active = current
        (output / f"{phase}.json").write_text(json.dumps(snapshot, indent=2) + "\n")
        # Small human-readable, screen-reader-friendly restitution, no colours.
        metrics = {"psi": snapshot["psi"], "alert_rate": snapshot["alert_rate"],
                   "observations_total": snapshot["observations_total"]}
        (output / f"{phase}.prom").write_text("".join(
            f"iddrv_sandbox_{name} {value}\n" for name, value in metrics.items()))
    (output / "local-file-test.json").write_text(json.dumps(events, indent=2) + "\n")
    (output / "README.txt").write_text(
        "Synthetic local sandbox only. No production scrape, recipient or acknowledgement.\n"
        "Reference: uniform synthetic scores; PSI > 0.25, alert rate > 0.20, minimum 100 observations.\n"
        "Scores are rankings, not probabilities. No feedback labels: no quality/calibration claim.\n"
        "JSON and Prometheus files can be reread; they do not restore process counters.\n")
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New isolated evidence directory")
    args = parser.parse_args()
    run(args.output)
    print(f"Sandbox evidence: {args.output}; channel={CHANNEL}; no production notification")
