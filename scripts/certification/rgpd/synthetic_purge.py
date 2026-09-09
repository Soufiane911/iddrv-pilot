"""C4 teaching exercise ONLY: fresh in-memory SQLite, never application storage.

No DSN, environment, input fixture, path, upload access or PostgreSQL adapter.
The reduced tables are NOT the production MPD. Only workspace metadata is
simulated; all decisions are conservatively held, without claiming a legal duty.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import sqlite3

CONFIRMATION = "ERASE_SYNTHETIC_WORKSPACE_ONLY"
TABLES = ("sites", "users", "import_sessions", "import_session_files", "semantic_mapping_decisions")
POLICY_KEYS = {"context", "site_id", "cutoff_utc", "as_of_utc", "decision_policy", "status"}


def utc(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value):
        raise ValueError("utc_required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid_date") from None


def validate(policy):
    if not isinstance(policy, dict) or set(policy) != POLICY_KEYS:
        raise ValueError("incomplete_or_unknown_policy")
    if (policy["context"] != "synthetic-workspace-v1" or
            type(policy["site_id"]) is not int or policy["site_id"] not in (1, 2) or
            policy["decision_policy"] != "preserve_all" or policy["status"] != "failed"):
        raise ValueError("unsupported_policy")
    cutoff, now = utc(policy["cutoff_utc"]), utc(policy["as_of_utc"])
    if cutoff >= now:
        raise ValueError("cutoff_must_precede_as_of")
    return cutoff


def example_policy():
    # Scenario boundary, NOT an approved retention period.
    return dict(context="synthetic-workspace-v1", site_id=1,
                cutoff_utc="2026-01-01T00:00:00Z", as_of_utc="2026-02-01T00:00:00Z",
                decision_policy="preserve_all", status="failed")


class SyntheticExercise:
    def __init__(self):
        self._db = sqlite3.connect(":memory:")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
            CREATE TABLE sites(id INTEGER PRIMARY KEY);
            CREATE TABLE users(id TEXT PRIMARY KEY);
            CREATE TABLE import_sessions(
                id TEXT PRIMARY KEY, site_id INTEGER NOT NULL REFERENCES sites(id),
                created_by TEXT REFERENCES users(id), status TEXT NOT NULL,
                updated_at TEXT NOT NULL);
            CREATE TABLE import_session_files(
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES import_sessions(id),
                file_name TEXT NOT NULL);
            CREATE TABLE semantic_mapping_decisions(
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES import_sessions(id),
                file_id TEXT REFERENCES import_session_files(id));
        """)
        self._db.executemany("INSERT INTO sites VALUES (?)", [(1,), (2,)])
        self._db.execute("INSERT INTO users VALUES ('synthetic-user')")
        rows = [("old", 1, "failed", "2025-12-31T23:59:59Z"),
                ("boundary", 1, "failed", "2026-01-01T00:00:00+00:00"),
                ("new", 1, "failed", "2026-01-01T00:00:01Z"),
                ("held", 1, "failed", "2025-01-01T00:00:00Z"),
                ("active", 1, "profiling", "2025-01-01T00:00:00Z"),
                ("other-site", 2, "failed", "2025-01-01T00:00:00Z")]
        for key, site, status, timestamp in rows:
            self._db.execute("INSERT INTO import_sessions VALUES (?,?,'synthetic-user',?,?)", (key, site, status, timestamp))
            self._db.execute("INSERT INTO import_session_files VALUES (?,?,?)", (key + "-file", key, "synthetic.xlsx"))
        self._db.execute("INSERT INTO semantic_mapping_decisions VALUES ('held-decision','held','held-file')")
        self._db.commit()

    def close(self):
        self._db.close()

    def snapshot(self):
        # Fixed allowlist only, never interpolated user-supplied identifiers.
        return {table: self._db.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall() for table in TABLES}

    def run(self, policy, *, execute=False, confirmation=None, fail_after_files=False):
        cutoff = validate(policy)
        if type(execute) is not bool or (execute and confirmation != CONFIRMATION):
            raise ValueError("synthetic_confirmation_required")
        before = self.snapshot()
        self._db.execute("BEGIN")
        try:
            rows = self._db.execute("SELECT id, updated_at FROM import_sessions WHERE site_id=? AND status=?", (policy["site_id"], policy["status"])).fetchall()
            eligible, held = [], 0
            for key, timestamp in rows:
                if utc(timestamp) >= cutoff:
                    continue
                # Protect both decision references: SQL 005 does not enforce that
                # file_id belongs to decision.session_id. Do not cascade blindly.
                protected = self._db.execute("""SELECT count(*) FROM semantic_mapping_decisions d
                    WHERE d.session_id=? OR d.file_id IN
                    (SELECT id FROM import_session_files WHERE session_id=?)""", (key, key)).fetchone()[0]
                if protected:
                    held += 1
                else:
                    eligible.append(key)
            file_count = sum(self._db.execute("SELECT count(*) FROM import_session_files WHERE session_id=?", (key,)).fetchone()[0] for key in eligible)
            if execute:
                for key in eligible:
                    self._db.execute("DELETE FROM import_session_files WHERE session_id=?", (key,))
                    if fail_after_files:
                        raise RuntimeError("synthetic_injected_failure")
                    self._db.execute("DELETE FROM import_sessions WHERE id=? AND site_id=?", (key, policy["site_id"]))
                if self._db.execute("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("synthetic_integrity_failure")
                self._db.commit()
            else:
                self._db.rollback()  # SELECT only after initial synthetic seed.
            after = self.snapshot()
            return {"context": "synthetic-workspace-v1", "mode": "execute" if execute else "dry-run",
                    "site_id": policy["site_id"], "candidate_sessions": len(eligible),
                    "candidate_files": file_count, "held_sessions": held,
                    "before_counts": {t: len(before[t]) for t in TABLES},
                    "after_counts": {t: len(after[t]) for t in TABLES},
                    "unchanged": before == after}
        except Exception:
            self._db.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-json", required=True, help="Explicit JSON policy, no path or DSN")
    parser.add_argument("--execute-synthetic", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    exercise = None
    try:
        policy = json.loads(args.policy_json)
        validate(policy)
        exercise = SyntheticExercise()
        print(json.dumps(exercise.run(policy, execute=args.execute_synthetic, confirmation=args.confirm), sort_keys=True))
        return 0
    except (ValueError, RuntimeError, sqlite3.Error):
        # Never echo arbitrary input, SQL, filenames, secrets or raw exceptions.
        print(json.dumps({"error": "synthetic_exercise_refused"}))
        return 2
    finally:
        if exercise:
            exercise.close()


if __name__ == "__main__":
    raise SystemExit(main())
