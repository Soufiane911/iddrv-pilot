from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from ingest.probe import probe_file
from ingest.watcher import (
    ImportJob,
    WatchedFolderWorker,
    WatcherConfig,
    heartbeat_is_fresh,
    site_id_for_path,
    source_kind_for_path,
)


@dataclass
class FakeStore:
    jobs: dict[str, ImportJob]
    hashes: dict[str, ImportJob]
    events: list[tuple[str, str]]

    def __init__(self):
        self.jobs = {}
        self.hashes = {}
        self.events = []
        self._counter = 0

    def claim(self, *, file_hash, source_path, source_kind, file_name, site_id, max_attempts, metadata, now):
        key = (site_id, file_hash)
        existing = self.hashes.get(key)
        if existing:
            if existing.status in {"completed", "quarantined"}:
                return existing, True
            if existing.status == "processing":
                return None, False
            existing.status = "processing"
            existing.attempt_count += 1
            return existing, False
        self._counter += 1
        job = ImportJob(
            id=f"job-{self._counter}", site_id=site_id, source_kind=source_kind,
            file_name=file_name, source_path=str(source_path), status="processing",
            file_hash=file_hash, attempt_count=1, max_attempts=max_attempts,
            metadata=dict(metadata),
        )
        self.jobs[job.id] = job
        self.hashes[key] = job
        return job, False

    def event(self, job_id, event_type, **kwargs):
        self.events.append((job_id, event_type))

    def set_paths(self, job, *, processing_path=None, archive_path=None, quarantine_path=None):
        if processing_path:
            job.processing_path = str(processing_path)
        if archive_path:
            job.archive_path = str(archive_path)
        if quarantine_path:
            job.quarantine_path = str(quarantine_path)
        return job

    def complete(self, job, *, passport_id=None):
        job.status = "completed"
        job.passport_id = passport_id
        return job

    def fail(self, job, *, error_code, error, backoff_seconds, now):
        job.last_error_code = error_code
        job.last_error = error
        job.status = "quarantined" if job.attempt_count >= job.max_attempts else "retry_wait"
        return job

    def processing_jobs(self):
        return [job for job in self.jobs.values() if job.status == "processing"]

    def requeue_processing(self, job, *, reason, now=None):
        job.status = "retry_wait"
        return job


def test_watcher_archives_duplicate_and_triggers_only_after_commit(tmp_path: Path):
    inbox = tmp_path / "inbox" / "site-1" / "machine" / "1003"
    inbox.mkdir(parents=True)
    source = inbox / "machine_cycles_1003.csv"
    source.write_text("Timestamp,Cycle_Time\n2026-07-10T10:00:00Z,2.5\n", encoding="utf-8")
    store = FakeStore()
    triggered = []
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=0, max_attempts=3),
        store=store,
        importer=lambda path, job: {"transaction_committed": True, "passport_id": "p-1"},
        on_import_committed=lambda job, result: triggered.append(job.id),
    )

    assert worker.run_once() == ["completed"]
    assert triggered == ["job-1"]
    archived = list((tmp_path / "archive").rglob("*csv"))
    assert len(archived) == 1
    # Deposit an identical copy under a different inbox name/path.
    duplicate = tmp_path / "inbox" / "site-1" / "machine" / "1003" / "copy.csv"
    duplicate.write_bytes(archived[0].read_bytes())
    assert worker.run_once() == ["duplicate"]
    assert triggered == ["job-1"]
    assert any(event == "duplicate_ignored" for _, event in store.events)


def test_watcher_quarantines_invalid_file_after_max_attempts(tmp_path: Path):
    source_dir = tmp_path / "inbox" / "site-1" / "machine" / "1003"
    source_dir.mkdir(parents=True)
    source = source_dir / "machine_cycles_1003.csv"
    source.write_text("not-an-import", encoding="utf-8")
    store = FakeStore()
    triggered = []
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=0, max_attempts=1),
        store=store,
        importer=lambda path, job: (_ for _ in ()).throw(ValueError("invalid export")),
        on_import_committed=lambda job, result: triggered.append(job.id),
    )

    assert worker.run_once() == ["quarantined"]
    assert triggered == []
    assert list((tmp_path / "quarantine").rglob("*"))
    assert next(iter(store.jobs.values())).last_error_code == "import_failed"


def test_processing_destination_is_persisted_before_move(tmp_path: Path, monkeypatch):
    source_dir = tmp_path / "inbox" / "site-1" / "machine" / "1003"
    source_dir.mkdir(parents=True)
    source = source_dir / "machine_cycles_1003.csv"
    source.write_text("Timestamp,Cycle_Time\n2026-07-10T10:00:00Z,2.5\n", encoding="utf-8")
    store = FakeStore()
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=0),
        store=store,
        importer=lambda path, job: {"transaction_committed": True, "passport_id": "p-1"},
    )
    original_move = worker._move

    def checked_move(source_path, destination_path):
        if Path(destination_path).is_relative_to(tmp_path / "processing"):
            job = next(iter(store.jobs.values()))
            assert job.processing_path == str(destination_path)
        return original_move(source_path, destination_path)

    monkeypatch.setattr(worker, "_move", checked_move)
    assert worker.run_once() == ["completed"]


def test_watcher_retries_when_detector_fails_after_commit(tmp_path: Path):
    source_dir = tmp_path / "inbox" / "site-1" / "machine" / "1003"
    source_dir.mkdir(parents=True)
    source = source_dir / "machine_cycles_1003.csv"
    source.write_text("Timestamp,Cycle_Time\n2026-07-10T10:00:00Z,2.5\n", encoding="utf-8")
    store = FakeStore()
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=0, max_attempts=1, backoff_seconds=0),
        store=store,
        importer=lambda path, job: {"transaction_committed": True, "passport_id": "p-1"},
        on_import_committed=lambda job, result: (_ for _ in ()).throw(RuntimeError("detector unavailable")),
    )
    assert worker.run_once() == ["retry_wait"]
    assert worker.run_once() == ["retry_wait"]
    assert next(iter(store.jobs.values())).status == "retry_wait"
    assert any(event == "detector_trigger_failed" for _, event in store.events)


def test_watcher_never_quarantines_committed_reconciliation_retry(tmp_path: Path):
    source_dir = tmp_path / "inbox" / "site-1" / "erp"
    source_dir.mkdir(parents=True)
    source = source_dir / "erp.xlsx"
    source.write_text("placeholder", encoding="utf-8")
    store = FakeStore()
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=0, max_attempts=1, backoff_seconds=0),
        store=store,
        importer=lambda path, job: {
            "transaction_committed": True,
            "passport_id": "p-erp",
            "post_commit_error": "erp_reconciliation_failed:db unavailable",
        },
    )
    assert worker.run_once() == ["retry_wait"]
    assert worker.run_once() == ["retry_wait"]
    job = next(iter(store.jobs.values()))
    assert job.status == "retry_wait"
    assert job.attempt_count == 0


def test_watcher_treats_missing_commit_confirmation_as_failure(tmp_path: Path):
    source_dir = tmp_path / "inbox" / "site-1" / "machine" / "1003"
    source_dir.mkdir(parents=True)
    source = source_dir / "machine_cycles_1003.csv"
    source.write_text("Timestamp,Cycle_Time\n2026-07-10T10:00:00Z,2.5\n", encoding="utf-8")
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=0, max_attempts=1),
        store=FakeStore(),
        importer=lambda path, job: None,
    )
    assert worker.run_once() == ["quarantined"]
    assert [path for path in (tmp_path / "quarantine").rglob("*") if path.is_file()]


def test_site_is_resolved_from_inbox_path(tmp_path: Path):
    inbox = tmp_path / "inbox"
    source = inbox / "site-42" / "machine" / "1003" / "cycles.csv"
    source.parent.mkdir(parents=True)
    source.write_text("x", encoding="utf-8")
    assert site_id_for_path(source, inbox) == 42
    assert site_id_for_path(source, inbox, configured_site_id=42) == 42


def test_recovery_completes_job_when_archive_move_already_happened(tmp_path: Path):
    archive = tmp_path / "archive" / "site-1" / "machine" / "1003" / "file.csv"
    archive.parent.mkdir(parents=True)
    archive.write_text("done", encoding="utf-8")
    store = FakeStore()
    job = ImportJob(
        id="job-crash", site_id=1, source_kind="machine", file_name="file.csv",
        source_path=str(tmp_path / "inbox" / "file.csv"), status="processing",
        file_hash="abc", attempt_count=1, max_attempts=3,
        processing_path=str(tmp_path / "processing" / "file.csv"),
        archive_path=str(archive), passport_id="passport-1",
    )
    store.jobs[job.id] = job
    worker = WatchedFolderWorker(WatcherConfig(root=tmp_path), store=store)

    assert worker.recover_processing() == 1
    assert job.status == "completed"
    assert job.passport_id == "passport-1"


def test_watcher_accumulates_stability_across_five_second_polls(tmp_path: Path):
    source_dir = tmp_path / "inbox" / "site-1" / "machine" / "1003"
    source_dir.mkdir(parents=True)
    source = source_dir / "machine_cycles_1003.csv"
    source.write_text("Timestamp,Cycle_Time\n2026-07-10T10:00:00Z,2.5\n", encoding="utf-8")
    ticks = iter((0.0, 5.0, 10.0))
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=10, poll_seconds=5),
        store=FakeStore(),
        importer=lambda path, job: {"transaction_committed": True, "passport_id": "p-1"},
        clock=lambda: next(ticks),
    )
    assert worker.run_once() == ["waiting_stability"]
    assert worker.run_once() == ["waiting_stability"]
    assert worker.run_once() == ["completed"]


def test_watcher_waits_for_stable_file(tmp_path: Path):
    source_dir = tmp_path / "inbox" / "site-1" / "machine" / "1003"
    source_dir.mkdir(parents=True)
    source = source_dir / "machine_cycles_1003.csv"
    source.write_text("Timestamp,Cycle_Time\n2026-07-10T10:00:00Z,2.5\n", encoding="utf-8")
    store = FakeStore()
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=10),
        store=store,
        importer=lambda path, job: {"transaction_committed": True},
    )
    assert worker.run_once() == ["waiting_stability"]
    assert not store.jobs


def test_worker_writes_fresh_heartbeat(tmp_path: Path):
    worker = WatchedFolderWorker(
        WatcherConfig(root=tmp_path, stable_seconds=0),
        store=FakeStore(),
        importer=lambda path, job: {"transaction_committed": True},
    )
    heartbeat = tmp_path / "processing" / ".worker_heartbeat"
    assert not heartbeat.exists()
    assert worker.run_once() == []
    assert heartbeat.is_file()
    assert heartbeat_is_fresh(heartbeat, max_age_seconds=30)
    payload = heartbeat.read_text(encoding="utf-8")
    assert "pid" in payload
    assert "ts" in payload


def test_heartbeat_is_fresh_rejects_missing_or_stale(tmp_path: Path):
    missing = tmp_path / "missing.heartbeat"
    assert not heartbeat_is_fresh(missing, max_age_seconds=30)
    stale = tmp_path / "stale.heartbeat"
    stale.write_text("{}", encoding="utf-8")
    past = time.time() - 120
    os.utime(stale, (past, past))
    assert not heartbeat_is_fresh(stale, max_age_seconds=30)


def test_probe_is_read_only_and_reports_mapping_unknowns(tmp_path: Path):
    source = tmp_path / "export.csv"
    source.write_text(
        "Timestamp,Cycle_Time,Vendor_Parameter\n"
        "2026-07-10T10:00:00Z,2.5,abc\n",
        encoding="utf-8",
    )
    report = probe_file(source, site_id=1, machine_erp_ref="1003")
    assert report["read_only"] is True
    assert report["writes_database"] is False
    assert report["mapping"]["confidence"] > 0
    assert "Vendor_Parameter" in report["mapping"]["unknown_columns"]
    assert report["validation"]["valid"] is True


def test_source_kind_uses_site_source_folder(tmp_path: Path):
    source = tmp_path / "inbox" / "site-1" / "quality" / "export.csv"
    source.parent.mkdir(parents=True)
    assert source_kind_for_path(source, tmp_path / "inbox") == "quality"


def test_g4_g5_migration_contract_and_no_plaintext_seed():
    migration = Path("db/migrations/004_automation_and_control_plane.sql").read_text(encoding="utf-8")
    seed = Path("db/seed_data.sql").read_text(encoding="utf-8")
    for table in (
        "production_lines", "machine_layouts", "users", "user_site_roles",
        "sessions", "action_proposal_decisions", "import_jobs", "import_job_events",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
    assert "pg_try_advisory_xact_lock" in Path("ingest/watcher.py").read_text(encoding="utf-8")
    assert "password_hash" not in seed
    assert "INSERT INTO users" not in seed
