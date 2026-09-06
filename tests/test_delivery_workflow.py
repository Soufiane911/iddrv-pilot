from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/delivery.yml"
COMPOSE = ROOT / "deploy/compose.pilot.yml"
DEPLOY_SCRIPT = ROOT / "deploy/deploy-pilot.sh"


def test_delivery_copies_db_recursively_before_running_deploy_script():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    match = re.search(
        r"(?ms)^\s+scp (?P<options>.*?)\\\n"
        r"\s+deploy/compose\.pilot\.yml deploy/deploy-pilot\.sh db \\\n"
        r"\s+\"\$DEPLOY_USER@\$DEPLOY_HOST:\$DEPLOY_PATH/\"",
        workflow,
    )

    assert match, "the pilot deployment must copy its complete source set"
    assert re.search(r"(?:^|\s)-r(?:\s|$)", match.group("options")), (
        "scp must copy db recursively"
    )
    assert workflow.index("chmod 700 '$DEPLOY_PATH/deploy-pilot.sh'") > match.start()


def test_delivery_copy_layout_matches_pilot_consumers():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")
    deploy_script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert 'deploy/compose.pilot.yml deploy/deploy-pilot.sh db \\\n' in workflow
    assert '"$DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_PATH/"' in workflow
    assert 'docker compose -f "$DEPLOY_PATH/compose.pilot.yml"' in deploy_script
    assert 'cd "$DEPLOY_PATH"' in deploy_script
    assert "./db/init.sql:/docker-entrypoint-initdb.d/01_init.sql:ro" in compose
    assert "./db/seed_data.sql:/docker-entrypoint-initdb.d/02_seed.sql:ro" in compose
