import argparse
import sys
import json
import os
import psycopg2
from datetime import datetime, timezone


def _database_summary(db_url: str, downtime_threshold: int) -> tuple[dict[str, int], dict[str, float | int | None]]:
    """Read report values from the database instead of printing demo constants."""
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM machine_cycles")
            cycle_count = int(cursor.fetchone()[0] or 0)
            cursor.execute("SELECT MIN(time), MAX(time) FROM machine_cycles")
            first_at, last_at = cursor.fetchone()
            duration_s = (last_at - first_at).total_seconds() if first_at and last_at else None

            # Some installations do not have the optional downtime export.  Do
            # not turn that absence into invented event counts.
            cursor.execute("SELECT to_regclass('public.downtime_events')")
            has_downtime_table = cursor.fetchone()[0] is not None
            if not has_downtime_table:
                downtime = {"events": 0, "micro_stops": 0, "available": 0}
            else:
                cursor.execute(
                    """SELECT
                         COUNT(*) FILTER (
                           WHERE EXTRACT(EPOCH FROM (end_time - start_time)) >= %s
                         )::int,
                         COUNT(*) FILTER (
                           WHERE EXTRACT(EPOCH FROM (end_time - start_time)) < %s
                         )::int
                       FROM downtime_events
                       WHERE start_time IS NOT NULL AND end_time IS NOT NULL""",
                    (downtime_threshold, downtime_threshold),
                )
                events, micro_stops = cursor.fetchone()
                downtime = {"events": int(events or 0), "micro_stops": int(micro_stops or 0), "available": 1}
            return downtime, {"total_cycles": cycle_count, "duration_s": duration_s}
    finally:
        conn.close()


# We will set DB_URL in env before importing reconciler if passed
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile machine cycles with ERP orders and shifts.")
    parser.add_argument("--db-url", help="Database connection URL")
    parser.add_argument("--report", action="store_true", help="Generate performance report")
    parser.add_argument("--downtime-threshold", type=int, default=120, help="Downtime threshold in seconds")
    parser.add_argument("--simulate-drift", action="store_true", help="Simulate drift detection")

    args = parser.parse_args()

    if args.db_url:
        os.environ["WORKER_DATABASE_URL"] = args.db_url
        os.environ["DATABASE_URL"] = args.db_url

    try:
        from .reconciler import count_overlapping_production_orders, reconcile_existing_cycles
    except ImportError:
        from reconciler import count_overlapping_production_orders, reconcile_existing_cycles

    # This flag is intentionally a fixture for demonstrations, not a model
    # result.  Label it so CLI output cannot be mistaken for measured drift.
    if args.simulate_drift:
        print(json.dumps({"drift_detected": True, "p_value": 0.001, "simulated": True}))
        sys.exit(0)

    try:
        reconciled = reconcile_existing_cycles()
        overlap_count = count_overlapping_production_orders()
        if overlap_count:
            print(f"Warning: {overlap_count} overlapping production-order pair(s) detected.", file=sys.stderr)
        
        summary_db_url = os.environ.get("WORKER_DATABASE_URL") or args.db_url or os.environ.get("DATABASE_URL") or "postgresql://iddrv_user@localhost:5432/iddrv"
        downtime, summary = _database_summary(summary_db_url, args.downtime_threshold)
        if downtime["available"]:
            print(
                f"Downtime summary: {downtime['events']} event(s) >= {args.downtime_threshold}s; "
                f"{downtime['micro_stops']} micro-stop(s) below threshold."
            )
        else:
            print("Downtime summary: no downtime_events export is available; no events inferred.")

        if args.report:
            duration = "unknown" if summary["duration_s"] is None else f"{summary['duration_s']:.0f}s"
            print(f"Performance report: total cycles = {summary['total_cycles']}, observed duration = {duration}")
        else:
            print(f"Reconciliation successful: {reconciled} cycles reconciled")
            
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
