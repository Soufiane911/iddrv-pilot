from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ingest.probe import probe_file
from ingest.watcher import ImportJob, WatchedFolderWorker, WatcherConfig, source_kind_for_path


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
        existing = self.hashes.get(file_hash)
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
        self.hashes[file_hash] = job
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
