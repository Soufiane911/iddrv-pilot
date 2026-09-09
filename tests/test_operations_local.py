"""Operations tests: fake Docker executable, no daemon/network/database access."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def deployment(tmp_path, *, rollback=False, fail=False, compatible=True,
               scenario="success"):
    host = tmp_path / "host"
    fresh = not host.exists()
    host.mkdir(exist_ok=True)
    tools = tmp_path / "bin"
    tools.mkdir(exist_ok=True)
    docker = tools / "docker"
    docker.write_text('''#!/bin/sh
printf "%s\\n" "$*" >> "$DEPLOY_PATH/calls"
case "$*" in
  *"run --rm --no-deps migrate"*)
    if [ "$FAIL_MIGRATION" = true ]; then exit 9; fi;;
  *"up -d --no-deps"*)
    printf "%s\\n" "$IMAGE_TAG" > "$DEPLOY_PATH/runtime-tag"
    if [ "$SCENARIO" = runtime ]; then exit 10; fi;;
  *"exec -T api"*)
    if [ "$SCENARIO" = readiness ]; then exit 11; fi;;
esac
exit 0
''')
    # Avoid the real readiness retry delay without changing production timing.
    (tools / "sleep").write_text("#!/bin/sh\nexit 0\n")
    (tools / "sleep").chmod(0o700)
    docker.chmod(0o700)
    if fresh:
        (host / ".last-image-tag").write_text("a" * 40 + "\n")
        (host / ".previous-image-tag").write_text("b" * 40 + "\n")
        (host / "runtime-tag").write_text("a" * 40 + "\n")
    env = {**os.environ, "PATH": f"{tools}:{os.environ['PATH']}", "DEPLOY_PATH": str(host),
           "IMAGE_TAG": "c" * 40, "GHCR_OWNER": "local-test",
           "ROLLBACK_SCHEMA_COMPATIBLE": str(compatible).lower(),
           "FAIL_MIGRATION": str(fail).lower(), "SCENARIO": scenario}
    result = subprocess.run(["bash", str(ROOT / "deploy/deploy-pilot.sh"),
                             "rollback" if rollback else "deploy"],
                            env=env, capture_output=True, text=True)
    return host, result


def test_migration_failure_preserves_known_good_tags(tmp_path):
    host, result = deployment(tmp_path, fail=True)
    assert result.returncode == 9
    assert (host / ".last-image-tag").read_text().strip() == "a" * 40
    assert (host / ".previous-image-tag").read_text().strip() == "b" * 40
    assert "up -d --no-deps" not in (host / "calls").read_text()
    assert not (host / ".deploy-lock").exists()


def test_deploy_waits_for_all_runtime_services(tmp_path):
    host, result = deployment(tmp_path)
    assert result.returncode == 0, result.stderr
    calls = (host / "calls").read_text()
    assert "up -d --wait --wait-timeout 180 timescaledb redis" in calls
    assert "run --rm --no-deps migrate" in calls
    assert "up -d --no-deps --wait --wait-timeout 180 api worker collector scorer web" in calls
    assert "--abort-on-container-exit" not in calls
    assert (host / ".previous-image-tag").read_text().strip() == "a" * 40
    assert (host / ".last-image-tag").read_text().strip() == "c" * 40


def test_rollback_never_runs_migration_or_deletes_volumes(tmp_path):
    host, result = deployment(tmp_path, rollback=True)
    assert result.returncode == 0, result.stderr
    calls = (host / "calls").read_text()
    assert "migrate" not in calls
    assert " down " not in calls
    assert (host / ".last-image-tag").read_text().strip() == "b" * 40


def test_rollback_requires_schema_confirmation(tmp_path):
    host, result = deployment(tmp_path, rollback=True, compatible=False)
    assert result.returncode == 2
    assert not (host / "calls").exists()


@pytest.mark.parametrize("scenario,code", [("runtime", 10), ("readiness", 1),
                                           ("migration", 9)])
def test_failed_attempt_rollback_recovers_last_good(tmp_path, scenario, code):
    host, result = deployment(tmp_path, scenario=scenario, fail=scenario == "migration")
    assert result.returncode == code
    assert (host / "runtime-tag").read_text().strip() == ("a" if scenario == "migration" else "c") * 40
    assert (host / ".pending-image-tag").read_text().strip() == "c" * 40
    assert (host / ".last-image-tag").read_text().strip() == "a" * 40
    assert (host / ".previous-image-tag").read_text().strip() == "b" * 40
    (host / "calls").unlink()
    host, result = deployment(tmp_path, rollback=True)
    assert result.returncode == 0, result.stderr
    assert "migrate" not in (host / "calls").read_text()
    assert (host / "runtime-tag").read_text().strip() == "a" * 40
    assert (host / ".last-image-tag").read_text().strip() == "a" * 40
    assert (host / ".previous-image-tag").read_text().strip() == "b" * 40
    assert not (host / ".pending-image-tag").exists()
    assert not (host / ".deploy-lock").exists()


def test_successful_deploy_then_normal_rollback(tmp_path):
    host, result = deployment(tmp_path)
    assert result.returncode == 0
    (host / "calls").unlink()
    host, result = deployment(tmp_path, rollback=True)
    assert result.returncode == 0, result.stderr
    assert "migrate" not in (host / "calls").read_text()
    assert (host / "runtime-tag").read_text().strip() == "a" * 40
    assert (host / ".previous-image-tag").read_text().strip() == "c" * 40
    assert not (host / ".pending-image-tag").exists()


def test_failed_recovery_can_be_retried(tmp_path):
    host, _ = deployment(tmp_path, scenario="runtime")
    _, result = deployment(tmp_path, rollback=True, scenario="readiness")
    assert result.returncode == 1
    assert (host / ".pending-image-tag").read_text().strip() == "a" * 40
    _, result = deployment(tmp_path, rollback=True)
    assert result.returncode == 0
    assert (host / ".last-image-tag").read_text().strip() == "a" * 40
    assert (host / ".previous-image-tag").read_text().strip() == "b" * 40


@pytest.mark.parametrize("tag_file", [".pending-image-tag", ".last-image-tag", ".previous-image-tag"])
def test_invalid_recorded_sha_refused(tmp_path, tag_file):
    host, _ = deployment(tmp_path, fail=True)
    (host / tag_file).write_text("invalid\n")
    (host / "calls").unlink()
    _, result = deployment(tmp_path, rollback=True)
    assert result.returncode == 2
    assert not (host / "calls").exists()
    assert (host / tag_file).read_text() == "invalid\n"


def test_recovery_requires_schema_confirmation(tmp_path):
    host, _ = deployment(tmp_path, scenario="runtime")
    (host / "calls").unlink()
    _, result = deployment(tmp_path, rollback=True, compatible=False)
    assert result.returncode == 2
    assert not (host / "calls").exists()
    assert (host / ".pending-image-tag").read_text().strip() == "c" * 40


def test_recovery_without_last_good_refused(tmp_path):
    host, _ = deployment(tmp_path, fail=True)
    (host / ".last-image-tag").unlink()
    (host / "calls").unlink()
    _, result = deployment(tmp_path, rollback=True)
    assert result.returncode == 2
    assert not (host / "calls").exists()


def test_existing_lock_refuses_recovery(tmp_path):
    host, _ = deployment(tmp_path, fail=True)
    (host / ".deploy-lock").mkdir()
    (host / "calls").unlink()
    _, result = deployment(tmp_path, rollback=True)
    assert result.returncode == 2
    assert not (host / "calls").exists()
    assert (host / ".deploy-lock").exists()


def test_pilot_telemetry_matches_main_runtime_contract():
    import yaml
    pilot = yaml.safe_load((ROOT / "deploy/compose.pilot.yml").read_text())["services"]
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    for name in ("collector", "scorer"):
        for field in ("command", "environment", "healthcheck", "depends_on"):
            assert pilot[name][field] == main[name][field]
        assert "ports" not in pilot[name]
        assert "OWNER_DATABASE_URL" not in pilot[name]["environment"]
    assert "healthcheck" in pilot["worker"]


def test_monitor_sandbox_collects_fires_recovers_and_rereads(tmp_path):
    spec = importlib.util.spec_from_file_location("monitor_local", ROOT / "deploy/monitor-local.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "evidence"
    events = module.run(output)
    assert len(events) == 4
    assert {e["channel"] for e in events} == {"local-file-test"}
    assert [e["state"] for e in events] == ["firing", "firing", "resolved", "resolved"]
    assert json.loads((output / "recovery.json").read_text())["psi"] == 0
    assert json.loads((output / "local-file-test.json").read_text()) == events
    assert module.evaluate({"recent_window": 0}) == ["insufficient_observations"]
    with pytest.raises(FileExistsError):
        module.run(output)
