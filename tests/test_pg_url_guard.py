import os
import stat
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pg_url_guard.py"


def run_guard(tmp_path, database_url, *extra):
    passfile = tmp_path / "pgpass"
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--passfile", str(passfile), *extra],
        env=env,
        capture_output=True,
        text=True,
    )
    return result, passfile


def test_guard_removes_password_from_cli_url_and_protects_passfile(tmp_path):
    result, passfile = run_guard(
        tmp_path,
        "postgresql://iddrv_user:p%40ss%3Aword@localhost:5432/iddrv?sslmode=disable",
        "--require-local",
    )

    assert result.returncode == 0
    assert "p%40ss" not in result.stdout
    assert result.stdout.strip() == "postgresql://iddrv_user@localhost:5432/iddrv?sslmode=disable"
    assert stat.S_IMODE(passfile.stat().st_mode) == 0o600
    assert passfile.read_text() == "localhost:5432:*:iddrv_user:p@ss\\:word\n"


def test_guard_rejects_query_routing_override(tmp_path):
    result, _ = run_guard(
        tmp_path,
        "postgresql://iddrv_user:secret@localhost:5432/iddrv?host=remote.example",
    )

    assert result.returncode == 2
    assert "secret" not in result.stderr
    assert "interdit" in result.stderr


def test_guard_rejects_remote_restore_target(tmp_path):
    result, _ = run_guard(
        tmp_path,
        "postgresql://iddrv_user:secret@db.example:5432/iddrv",
        "--require-local",
    )

    assert result.returncode == 2
    assert "distante" in result.stderr
