from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_gap_recovery_is_audited_and_keeps_history():
    migration = (ROOT / 'db/migrations/018_continuity_recovery.sql').read_text(encoding='utf-8')
    assert 'continuity_recovery_reviews' in migration
    assert 'last_validated_cursor' in migration
    assert 'available_from_sequence' in migration
    source = (ROOT / 'backend/app/api/machine_connections.py').read_text(encoding='utf-8')
    assert '/continuity' in source
    assert 'continuity_review_required' in source
    assert 'continuity_recovery_reviews' in source
    assert 'continuity_resume_stream_mismatch' in source
    assert 'server_stream != current' in source
    assert 'FOR UPDATE OF c' not in source
    assert 'FROM machine_stream_offsets WHERE connection_id=%s FOR UPDATE' in source
    assert 'TRUNCATE' not in source


def test_source_fixture_hides_retained_rows_without_deleting_sqlite_events():
    source = (ROOT / 'tests/fixtures/press_api/app.py').read_text(encoding='utf-8')
    assert 'retention_floor' in source
    assert 'oldest_available_at' in source
    assert 'sequence>=?' in source


def test_backup_restore_use_versioned_full_timescale_format():
    backup = (ROOT / 'scripts/backup.sh').read_text(encoding='utf-8')
    restore = (ROOT / 'scripts/restore.sh').read_text(encoding='utf-8')
    assert '--exclude-table-data=public.machine_cycles' in backup
    assert '--format=custom --no-owner' in backup
    assert 'iddrv-backup-version=2' in backup
    assert 'timescaledb_pre_restore' in restore
    assert 'timescaledb_post_restore' in restore
    assert '--no-privileges --exit-on-error' in restore
    assert '--data-only' not in restore
