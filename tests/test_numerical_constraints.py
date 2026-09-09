"""Guard the common artifact-compatible stack and its installation entrypoints."""
from pathlib import Path
import shlex

import pytest
from pip._internal.network.session import PipSession
from pip._internal.req.req_file import parse_requirements

ROOT = Path(__file__).resolve().parents[1]
KNOWN = {
    'numpy': '2.2.6', 'pandas': '2.3.3', 'scipy': '1.16.3',
    'scikit-learn': '1.7.2', 'joblib': '1.5.2',
}


@pytest.mark.parametrize('source', ['requirements.txt', 'backend/requirements.txt'])
@pytest.mark.parametrize('cwd', ['.', 'backend'])
def test_pip_resolves_common_constraints(source, cwd, monkeypatch):
    monkeypatch.chdir(ROOT / cwd)
    with PipSession() as session:
        parsed = list(parse_requirements(str(ROOT / source), session=session))
    constraints = {r.requirement for r in parsed if r.constraint}
    assert constraints == {f'{name}=={version}' for name, version in KNOWN.items()}
    assert all(Path(r.line_source.split(' of ', 1)[1]).resolve() ==
               ROOT / 'constraints-numerical.txt' for r in parsed if r.constraint)


def test_ci_install_sources_share_constraints():
    for workflow in ('ci.yml', 'model-delivery.yml'):
        text = (ROOT / '.github/workflows' / workflow).read_text()
        installs = [line for line in text.splitlines() if 'pip install' in line
                    and '--upgrade pip' not in line]
        assert installs
        for line in installs:
            tokens = shlex.split(line)
            sources = [tokens[i + 1] for i, token in enumerate(tokens) if token == '-r']
            assert sources and set(sources) <= {'requirements.txt', 'backend/requirements.txt'}
            assert not any(token.split('==')[0] in KNOWN for token in tokens)


def test_runtime_image_copies_constraints_before_install():
    docker = (ROOT / 'backend/Dockerfile').read_text()
    assert docker.index('COPY constraints-numerical.txt /app/constraints-numerical.txt') < docker.index('RUN pip install')
    assert '-r /app/backend/requirements.txt' in docker
    # Ingest workers use the same image; there is no independent ingest install.
    compose = (ROOT / 'docker-compose.yml').read_text()
    for service in ('api', 'worker', 'collector', 'scorer'):
        block = compose.split(f'  {service}:\n', 1)[1]
        assert 'dockerfile: backend/Dockerfile' in block.split('    restart:', 1)[0]
