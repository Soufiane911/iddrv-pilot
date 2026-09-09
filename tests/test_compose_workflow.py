"""CI Compose fixtures must cover required interpolation without local secrets."""
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_ci_supplies_all_required_variables():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    step = next(item for item in workflow['jobs']['compose']['steps']
                if item.get('name') == 'Validate docker-compose.yml')
    required = set(re.findall(r'\$\{([A-Z_][A-Z_0-9]*):\?',
                              (ROOT / 'docker-compose.yml').read_text()))
    assert required, 'Expected explicit Compose interpolation guards'
    assert required <= step['env'].keys()
    assert all(step['env'][key] for key in required)
    assert '--env-file /dev/null' in step['run']
    assert 'config --quiet' in step['run']
    urls = [step['env'][key] for key in
            ('OWNER_DATABASE_URL', 'API_DATABASE_URL', 'WORKER_DATABASE_URL')]
    assert len(set(urls)) == 3
    assert all('ci-validation-only@timescaledb:' in url for url in urls)
