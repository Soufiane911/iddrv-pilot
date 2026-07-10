"""Durable watched-folder ingestion worker.

The worker deliberately sits *around* the existing parsers in
``ingest_pipeline``.  It owns file lifecycle and retry state, while a parser
owns the database transaction for the business rows.  A successful callback
is therefore invoked only after the parser has returned successfully (and has
committed its own transaction).

The module has no scheduler dependency: ``run_once`` is suitable for a cron,
Docker health loop, or a future scheduler.  ``run_forever`` is a thin polling
loop for the on-prem pilot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from typing import Any, Callable, Iterable, Mapping


DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv",
)
RETRYABLE_STATUSES = {"discovered", "retry_wait", "failed"}
TERMINAL_STATUSES = {"completed", "quarantined"}
IGNORED_SUFFIXES = {".part", ".partial", ".tmp", ".lock", ".crdownload"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_sha256(path: Path) -> str:
    """Hash a stable file in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


@dataclass(frozen=True)
class WatcherConfig:
    """Filesystem and retry policy for one worker instance."""

    root: Path
    stable_seconds: float = 10.0
    poll_seconds: float = 5.0
    max_attempts: int = 3
    backoff_seconds: float = 30.0
    site_id: int | None = None
    db_url: str = DEFAULT_DB_URL

    def __post_init__(self) -> None:
        if self.stable_seconds < 0:
            raise ValueError("stable_seconds must be >= 0")
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be > 0")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be >= 0")

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def processing(self) -> Path:
        return self.root / "processing"

    @property
    def archive(self) -> Path:
        return self.root / "archive"

    @property
    def quarantine(self) -> Path:
        return self.root / "quarantine"

    def ensure_directories(self) -> None:
        for directory in (self.inbox, self.processing, self.archive, self.quarantine):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class FileObservation:
    size: int
    mtime_ns: int
    observed_at: float


@dataclass
class ImportJob:
    id: str
    site_id: int | None
    source_kind: str
    file_name: str
    source_path: str
    status: str
    file_hash: str | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    processing_path: str | None = None
    archive_path: str | None = None
    quarantine_path: str | None = None
    passport_id: str | None = None
    last_error_code: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ImportJob":
        return cls(
            id=str(row["id"]),
            site_id=row.get("site_id"),
            source_kind=str(row.get("source_kind") or "unknown"),
            file_name=str(row.get("file_name") or ""),
            source_path=str(row.get("source_path") or ""),
            status=str(row.get("status") or "discovered"),
            file_hash=row.get("file_hash"),
            attempt_count=int(row.get("attempt_count") or 0),
            max_attempts=int(row.get("max_attempts") or 3),
            processing_path=row.get("processing_path"),
            archive_path=row.get("archive_path"),
            quarantine_path=row.get("quarantine_path"),
            passport_id=str(row["passport_id"]) if row.get("passport_id") else None,
            last_error_code=row.get("last_error_code"),
            last_error=row.get("last_error"),
            metadata=dict(row.get("metadata") or {}),
        )


def _row_to_job(row: Any) -> ImportJob:
    if isinstance(row, Mapping):
        return ImportJob.from_row(row)
    # Useful for tests using a simple tuple cursor.  The order mirrors the
    # SELECT in ImportJobStore._select_job.
    columns = (
        "id", "site_id", "source_kind", "file_name", "source_path", "status",
        "file_hash", "attempt_count", "max_attempts", "processing_path",
        "archive_path", "quarantine_path", "passport_id", "last_error_code",
        "last_error", "metadata",
    )
    return ImportJob.from_row(dict(zip(columns, row)))


def _scalar(row: Any) -> Any:
    """Read a one-column result from tuple or RealDict cursors."""
    if isinstance(row, Mapping):
        return next(iter(row.values()))
    return row[0]


class ImportJobStore:
    """PostgreSQL persistence for the durable file state machine.

    ``connection_factory`` is intentionally injectable so all worker logic can
    be tested without a live database.  Production uses ``psycopg2.connect``.
    """

    _SELECT_COLUMNS = """
        id, site_id, source_kind, file_name, source_path, status,
        file_hash, attempt_count, max_attempts, processing_path,
        archive_path, quarantine_path, passport_id, last_error_code,
        last_error, metadata
    """

    def __init__(self, db_url: str = DEFAULT_DB_URL, connection_factory: Callable | None = None):
        self.db_url = db_url
        self._connection_factory = connection_factory

    def connect(self):
        if self._connection_factory:
            return self._connection_factory()
        import psycopg2

        return psycopg2.connect(self.db_url)

    def _select_job(self, cursor, job_id: str) -> ImportJob | None:
        cursor.execute(f"SELECT {self._SELECT_COLUMNS} FROM import_jobs WHERE id = %s", (job_id,))
        row = cursor.fetchone()
        return _row_to_job(row) if row else None

    def claim(
        self,
        *,
        file_hash: str,
        source_path: Path,
        source_kind: str,
        file_name: str,
        site_id: int | None,
        max_attempts: int,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> tuple[ImportJob | None, bool]:
        """Atomically claim a hash.

        Returns ``(job, duplicate)``.  ``job is None`` means another worker
        currently owns the row or its retry backoff has not elapsed.
        """
        now = now or utc_now()
        metadata_json = _json(dict(metadata or {}))
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    # Transaction-scoped advisory lock makes the hash claim
                    # explicit and complements SELECT ... FOR UPDATE.
                    cursor.execute(
                        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0))",
                        (file_hash,),
                    )
                    if not _scalar(cursor.fetchone()):
                        return None, False

                    cursor.execute(
                        f"SELECT {self._SELECT_COLUMNS} FROM import_jobs "
                        "WHERE file_hash = %s FOR UPDATE",
                        (file_hash,),
                    )
                    row = cursor.fetchone()
                    if row:
                        job = _row_to_job(row)
                        if job.status in TERMINAL_STATUSES:
                            return job, True
                        # A processing row is owned by a live or previously
                        # crashed worker.  Recovery handles it on next start.
                        if job.status == "processing":
                            return None, False
                        if job.status == "retry_wait":
                            cursor.execute(
                                "SELECT next_attempt_at <= %s FROM import_jobs WHERE id = %s",
                                (now, job.id),
                            )
                            if not _scalar(cursor.fetchone()):
                                return None, False
                        attempt = job.attempt_count + 1
                        cursor.execute(
                            """
                            UPDATE import_jobs
                               SET status='processing', attempt_count=%s,
                                   max_attempts=%s, source_path=%s,
                                   file_name=%s, site_id=%s,
                                   next_attempt_at=%s, started_at=%s,
                                   updated_at=%s, last_error_code=NULL,
                                   last_error=NULL, metadata=%s::jsonb
                             WHERE id=%s
                         RETURNING id, site_id, source_kind, file_name,
                                   source_path, status, file_hash,
                                   attempt_count, max_attempts,
                                   processing_path, archive_path,
                                   quarantine_path, passport_id,
                                   last_error_code, last_error, metadata
                            """,
                            (attempt, max_attempts, str(source_path), file_name,
                             site_id, now, now, now, metadata_json, job.id),
                        )
                        return _row_to_job(cursor.fetchone()), False

                    cursor.execute(
                        """
                        INSERT INTO import_jobs (
                            site_id, source_kind, file_name, source_path,
                            file_hash, status, attempt_count, max_attempts,
                            next_attempt_at, metadata, started_at, updated_at
                        ) VALUES (%s,%s,%s,%s,%s,'processing',1,%s,%s,%s::jsonb,%s,%s)
                        RETURNING id, site_id, source_kind, file_name,
                                  source_path, status, file_hash,
                                  attempt_count, max_attempts,
                                  processing_path, archive_path,
                                  quarantine_path, passport_id,
                                  last_error_code, last_error, metadata
                        """,
                        (site_id, source_kind, file_name, str(source_path), file_hash,
                         max_attempts, now, metadata_json, now, now),
                    )
                    return _row_to_job(cursor.fetchone()), False
        finally:
            conn.close()

    def event(
        self,
        job_id: str,
        event_type: str,
        *,
        status: str | None = None,
        attempt: int = 0,
        source_path: str | None = None,
        destination_path: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO import_job_events
                          (job_id, attempt, event_type, status, source_path,
                           destination_path, detail)
                        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                        """,
                        (job_id, attempt, event_type, status, source_path,
                         destination_path, _json(dict(detail or {}))),
                    )
        finally:
            conn.close()

    def set_paths(self, job: ImportJob, *, processing_path: Path | None = None,
                  archive_path: Path | None = None, quarantine_path: Path | None = None) -> ImportJob:
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE import_jobs
                           SET processing_path=COALESCE(%s, processing_path),
                               archive_path=COALESCE(%s, archive_path),
                               quarantine_path=COALESCE(%s, quarantine_path),
                               updated_at=NOW()
                         WHERE id=%s
                        """,
                        (str(processing_path) if processing_path else None,
                         str(archive_path) if archive_path else None,
                         str(quarantine_path) if quarantine_path else None,
                         job.id),
                    )
            if processing_path:
                job.processing_path = str(processing_path)
            if archive_path:
                job.archive_path = str(archive_path)
            if quarantine_path:
                job.quarantine_path = str(quarantine_path)
            return job
        finally:
            conn.close()

    def set_source_path(self, job: ImportJob, source_path: Path) -> ImportJob:
        """Keep the logical source location accurate after crash recovery."""
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE import_jobs SET source_path=%s, updated_at=NOW() WHERE id=%s",
                        (str(source_path), job.id),
                    )
            job.source_path = str(source_path)
            return job
        finally:
            conn.close()

    def complete(self, job: ImportJob, *, passport_id: str | None = None) -> ImportJob:
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE import_jobs
                           SET status='completed', passport_id=COALESCE(%s, passport_id),
                               completed_at=NOW(), updated_at=NOW()
                         WHERE id=%s
                        """,
                        (passport_id, job.id),
                    )
            job.status = "completed"
            if passport_id:
                job.passport_id = passport_id
            return job
        finally:
            conn.close()

    def fail(self, job: ImportJob, *, error_code: str, error: str,
             backoff_seconds: float, now: datetime | None = None) -> ImportJob:
        now = now or utc_now()
        terminal = job.attempt_count >= job.max_attempts
        status = "quarantined" if terminal else "retry_wait"
        next_attempt = now if terminal else now + timedelta(
            seconds=backoff_seconds * (2 ** max(0, job.attempt_count - 1))
        )
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE import_jobs
                           SET status=%s, next_attempt_at=%s,
                               last_error_code=%s, last_error=%s, updated_at=NOW()
                         WHERE id=%s
                        """,
                        (status, next_attempt, error_code, error[:8000], job.id),
                    )
            job.status = status
            job.last_error_code = error_code
            job.last_error = error[:8000]
            return job
        finally:
            conn.close()

    def requeue_processing(self, job: ImportJob, *, reason: str,
                           now: datetime | None = None) -> ImportJob:
        now = now or utc_now()
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE import_jobs
                           SET status='retry_wait', next_attempt_at=%s,
                               last_error_code='worker_restart', last_error=%s,
                               updated_at=NOW()
                         WHERE id=%s AND status='processing'
                        """,
                        (now, reason[:8000], job.id),
                    )
            job.status = "retry_wait"
            return job
        finally:
            conn.close()

    def processing_jobs(self) -> list[ImportJob]:
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT {self._SELECT_COLUMNS} FROM import_jobs "
                        "WHERE status='processing' ORDER BY started_at"
                    )
                    return [_row_to_job(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def list_jobs(self, *, limit: int = 100, site_id: int | None = None) -> list[dict[str, Any]]:
        """Read model used by the API import status page."""
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    clauses = []
                    args: list[Any] = []
                    if site_id is not None:
                        clauses.append("site_id=%s")
                        args.append(site_id)
                    where = " WHERE " + " AND ".join(clauses) if clauses else ""
                    args.append(max(1, min(limit, 500)))
                    cursor.execute(
                        f"SELECT {self._SELECT_COLUMNS}, discovered_at, started_at, "
                        "completed_at, next_attempt_at FROM import_jobs" + where +
                        " ORDER BY discovered_at DESC LIMIT %s", args,
                    )
                    rows = cursor.fetchall()
                    names = [description[0] for description in cursor.description]
                    return [dict(zip(names, row)) if not isinstance(row, Mapping) else dict(row) for row in rows]
        finally:
            conn.close()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT {self._SELECT_COLUMNS}, discovered_at, started_at, "
                        "completed_at, next_attempt_at FROM import_jobs WHERE id=%s",
                        (job_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    if isinstance(row, Mapping):
                        return dict(row)
                    return dict(zip([d[0] for d in cursor.description], row))
        finally:
            conn.close()


def source_kind_for_path(path: Path, inbox_root: Path) -> str:
    """Infer a conservative source kind from folder/name, never from content."""
    stem = path.stem.lower()
    try:
        relative_parts = {part.lower() for part in path.resolve().relative_to(inbox_root.resolve()).parts[:-1]}
    except ValueError:
        relative_parts = set()
    if "quality" in stem or "quality" in relative_parts:
        return "quality"
    if "maintenance" in stem or "maint" in stem or "maintenance" in relative_parts or "maint" in relative_parts:
        return "maintenance"
    if "operator" in stem or "note" in stem or "operator" in relative_parts or "notes" in relative_parts:
        return "operator_note"
    if "erp" in stem or path.suffix.lower() in {".xlsx", ".xls"}:
        return "erp_order"
    if "cycle" in stem or path.suffix.lower() in {".csv", ".txt", ".tsv"}:
        return "machine_cycle"
    return "unknown"


def machine_ref_for_path(path: Path) -> str | None:
    """Read a machine reference from a source folder or conventional filename."""
    for component in reversed(path.parts[:-1]):
        if re.fullmatch(r"\d{1,8}", component):
            return component
    match = re.search(r"(?:machine|presse|press)[_-]?(\d{1,8})", path.stem, re.IGNORECASE)
    return match.group(1) if match else None


def _safe_relative(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes watcher root: {path}") from exc


class WatchedFolderWorker:
    """Poll, claim and import files from ``inbox``."""

    def __init__(
        self,
        config: WatcherConfig,
        *,
        store: ImportJobStore | Any | None = None,
        importer: Callable[[Path, ImportJob], Any] | None = None,
        on_import_committed: Callable[[ImportJob, Any], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = utc_now,
    ):
        self.config = config
        self.config.ensure_directories()
        self.store = store or ImportJobStore(config.db_url)
        self.importer = importer or self._default_importer
        self.on_import_committed = on_import_committed
        self._clock = clock
        self._now = now
        self._observations: dict[str, FileObservation] = {}

    def _is_stable(self, path: Path) -> bool:
        stat = path.stat()
        key = str(path.resolve())
        current = FileObservation(stat.st_size, stat.st_mtime_ns, self._clock())
        previous = self._observations.get(key)
        self._observations[key] = current
        if self.config.stable_seconds == 0:
            return True
        if not previous:
            return False
        return (
            previous.size == current.size
            and previous.mtime_ns == current.mtime_ns
            and current.observed_at - previous.observed_at >= self.config.stable_seconds
        )

    def _scan(self) -> list[Path]:
        self.config.ensure_directories()
        root = self.config.inbox.resolve()
        files: list[Path] = []
        for path in sorted(self.config.inbox.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if path.name.startswith(".") or path.suffix.lower() in IGNORED_SUFFIXES:
                continue
            try:
                path.resolve().relative_to(root)
            except ValueError:
                continue
            files.append(path)
        return files

    def _destination(self, root: Path, source: Path, *, suffix: str | None = None) -> Path:
        relative = _safe_relative(source, self.config.inbox)
        if suffix:
            relative = relative.with_name(relative.name + suffix)
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    @staticmethod
    def _move(source: Path, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            # A copied duplicate should never overwrite the first evidence.
            destination = destination.with_name(
                f"{destination.stem}.{int(time.time() * 1000)}{destination.suffix}"
            )
        shutil.move(str(source), str(destination))
        return destination

    def _default_importer(self, path: Path, job: ImportJob) -> Any:
        """Adapt the existing transactional import functions.

        Machine files must carry their machine ERP reference in a parent folder
        (``.../inbox/site/machine/1003/file.csv``) or in their filename.  This
        fails closed instead of guessing a machine.
        """
        from . import ingest_pipeline

        if job.source_kind == "erp_order":
            return ingest_pipeline.ingest_erp_file(str(path))
        if job.source_kind in {"quality", "maintenance", "operator_note"}:
            kind = {"quality": "quality", "maintenance": "maintenance", "operator_note": "notes"}[job.source_kind]
            return ingest_pipeline.ingest_context_file(str(path), kind)
        if job.source_kind == "machine_cycle":
            machine_ref = machine_ref_for_path(path)
            if not machine_ref:
                raise ValueError(
                    "machine_ref_missing: place the file under a numeric machine folder "
                    "or use machine_<erp_ref> in the filename"
                )
            return ingest_pipeline.ingest_machine_file(str(path), machine_ref)
        raise ValueError(f"unsupported_source_kind:{job.source_kind}")

    def _event(self, job: ImportJob, event_type: str, **kwargs: Any) -> None:
        try:
            self.store.event(job.id, event_type, attempt=job.attempt_count, **kwargs)
        except Exception:
            # Event logging must not hide the import outcome.  The primary
            # import state remains durable in import_jobs.
            pass

    def recover_processing(self) -> int:
        """Return interrupted processing files to inbox for a safe retry."""
        recovered = 0
        for job in self.store.processing_jobs():
            if not job.processing_path:
                self.store.requeue_processing(job, reason="processing_path_missing")
                self._event(job, "worker_restart", status="retry_wait", detail={"reason": "processing_path_missing"})
                recovered += 1
                continue
            processing = Path(job.processing_path)
            if processing.exists():
                relative = _safe_relative(processing, self.config.processing)
                destination = self.config.inbox / relative
                moved = self._move(processing, destination)
                job.source_path = str(destination)
                if hasattr(self.store, "set_source_path"):
                    self.store.set_source_path(job, destination)
                self.store.requeue_processing(job, reason="worker_restart")
                self._event(job, "worker_restart", status="retry_wait", source_path=str(processing), destination_path=str(moved))
                recovered += 1
            else:
                self.store.requeue_processing(job, reason="processing_file_missing")
                self._event(job, "worker_restart", status="retry_wait", detail={"reason": "processing_file_missing"})
                recovered += 1
        return recovered

    def process_file(self, source: Path) -> str:
        """Process one stable inbox file and return a compact outcome."""
        if not source.exists() or not self._is_stable(source):
            return "waiting_stability"

        file_hash = compute_sha256(source)
        relative = _safe_relative(source, self.config.inbox)
        source_kind = source_kind_for_path(source, self.config.inbox)
        metadata = {
            "relative_path": relative.as_posix(),
            "machine_erp_ref": machine_ref_for_path(source),
        }
        job, duplicate = self.store.claim(
            file_hash=file_hash,
            source_path=source,
            source_kind=source_kind,
            file_name=source.name,
            site_id=self.config.site_id,
            max_attempts=self.config.max_attempts,
            metadata=metadata,
            now=self._now(),
        )
        if job is None:
            return "busy_or_backoff"

        if duplicate:
            archive = self._destination(self.config.archive, source, suffix=f".duplicate.{file_hash[:12]}")
            moved = self._move(source, archive)
            self.store.set_paths(job, archive_path=moved)
            self._event(job, "duplicate_ignored", status=job.status, source_path=str(source), destination_path=str(moved), detail={"file_hash": file_hash})
            return "duplicate"

        processing = self._destination(self.config.processing, source)
        moved_processing = self._move(source, processing)
        self.store.set_paths(job, processing_path=moved_processing)
        self._event(job, "claimed", status="processing", source_path=str(source), destination_path=str(moved_processing))

        result: Any = None
        try:
            result = self.importer(moved_processing, job)
            passport_id = None
            if isinstance(result, Mapping):
                passport_id = result.get("passport_id")
                if result.get("transaction_committed") is False:
                    raise RuntimeError("importer returned transaction_committed=false")
            completed = self.store.complete(job, passport_id=passport_id)
            self._event(completed, "import_committed", status="completed", source_path=str(moved_processing), detail={"passport_id": passport_id})
            # This is deliberately after complete(): detectors never observe a
            # job that is still marked processing or retry_wait.
            if self.on_import_committed:
                try:
                    self.on_import_committed(completed, result)
                    self._event(completed, "detectors_triggered", status="completed")
                except Exception as trigger_error:
                    self._event(completed, "detector_trigger_failed", status="completed", detail={"error": str(trigger_error)})
            archive = self._destination(self.config.archive, source)
            moved_archive = self._move(moved_processing, archive)
            self.store.set_paths(completed, archive_path=moved_archive)
            self._event(completed, "archived", status="completed", source_path=str(moved_processing), destination_path=str(moved_archive))
            return "completed"
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            traceback_text = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            failed = self.store.fail(
                job,
                error_code="import_failed",
                error=traceback_text or error,
                backoff_seconds=self.config.backoff_seconds,
                now=self._now(),
            )
            if failed.status == "quarantined":
                quarantine = self._destination(self.config.quarantine, source, suffix=f".{file_hash[:12]}")
                moved = self._move(moved_processing, quarantine)
                self.store.set_paths(failed, quarantine_path=moved)
                self._event(failed, "quarantined", status="quarantined", source_path=str(moved_processing), destination_path=str(moved), detail={"error": error})
                return "quarantined"
            retry_source = self._destination(self.config.inbox, source)
            moved = self._move(moved_processing, retry_source)
            if hasattr(self.store, "set_source_path"):
                self.store.set_source_path(failed, moved)
            self._event(failed, "retry_scheduled", status="retry_wait", source_path=str(moved_processing), destination_path=str(moved), detail={"error": error})
            return "retry_wait"

    def run_once(self) -> list[str]:
        self.recover_processing()
        outcomes = []
        for source in self._scan():
            try:
                outcomes.append(self.process_file(source))
            except Exception as exc:
                # A malformed path or an unavailable DB should be visible to a
                # caller but should not stop the next file from being observed.
                outcomes.append(f"worker_error:{type(exc).__name__}")
        return outcomes

    def run_forever(self, stop_event: Event | None = None) -> None:
        stop_event = stop_event or Event()
        while not stop_event.is_set():
            self.run_once()
            stop_event.wait(self.config.poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IDDVR watched-folder ingestion worker")
    parser.add_argument("--root", default=os.getenv("INGEST_WATCH_ROOT", "data/watch"), help="watch root containing inbox/processing/archive/quarantine")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL)
    parser.add_argument("--site-id", type=int, default=None)
    parser.add_argument("--stable-seconds", type=float, default=10.0)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--backoff-seconds", type=float, default=30.0)
    parser.add_argument("--once", action="store_true", help="scan once and exit")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    worker = WatchedFolderWorker(
        WatcherConfig(
            root=Path(args.root), db_url=args.db_url, site_id=args.site_id,
            stable_seconds=args.stable_seconds, poll_seconds=args.poll_seconds,
            max_attempts=args.max_attempts, backoff_seconds=args.backoff_seconds,
        )
    )
    if args.once:
        print(_json({"outcomes": worker.run_once()}))
    else:
        worker.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
