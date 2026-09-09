"""Execute the real reporting shell with mocked GitHub contexts, never delivery jobs."""
import itertools
import os
from pathlib import Path
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / '.github/workflows/delivery.yml').read_text()
JOB = WORKFLOW.split('  deployment-status:\n', 1)[1]
# Reporting is the final job: execute its exact literal run block without a
# YAML dependency absent from the CI requirements. Wiring is checked below.
SCRIPT = textwrap.dedent(JOB.split('        run: |\n', 1)[1])
STATES = ('success', 'failure', 'cancelled', 'skipped')


def run_report(tmp_path, ci, build, deploy, promotion='true', sha='a' * 40):
    summary = tmp_path / 'summary'
    env = {
        'PATH': os.environ['PATH'],
        'GITHUB_STEP_SUMMARY': str(summary),
        'CI_RESULT': ci, 'BUILD_RESULT': build, 'DEPLOY_RESULT': deploy,
        'PROMOTION_ENABLED': promotion, 'VALIDATED_SHA': sha,
    }
    result = subprocess.run(
        ['bash', '-c', SCRIPT], env=env, cwd=tmp_path,
        capture_output=True, text=True, timeout=5,
    )
    assert summary.read_text() == result.stdout
    return result


def test_workflow_context_wiring_and_execution_guards():
    assert '    if: always()\n' in JOB
    assert '    needs: [build-and-push, deploy]\n' in JOB
    expected_env = {
        'CI_RESULT': '${{ github.event.workflow_run.conclusion }}',
        'BUILD_RESULT': '${{ needs.build-and-push.result }}',
        'DEPLOY_RESULT': '${{ needs.deploy.result }}',
        'PROMOTION_ENABLED': '${{ vars.DEPLOY_ENABLED }}',
        'VALIDATED_SHA': '${{ github.event.workflow_run.head_sha }}',
    }
    for key, value in expected_env.items():
        assert f'          {key}: {value}\n' in JOB
    assert '${{' not in SCRIPT
    assert "    if: github.event.workflow_run.conclusion == 'success'\n" in WORKFLOW
    assert '    needs: build-and-push\n' in WORKFLOW
    assert "    if: github.event.workflow_run.conclusion == 'success' && vars.DEPLOY_ENABLED == 'true'\n" in WORKFLOW
    assert 'continue-on-error' not in WORKFLOW


@pytest.mark.parametrize('ci,build,deploy,promotion', itertools.product(STATES, STATES, STATES, ('true', 'false', '')))
def test_reporting_matrix(tmp_path, ci, build, deploy, promotion):
    result = run_report(tmp_path, ci, build, deploy, promotion)
    actual_failure = build in ('failure', 'cancelled') or deploy in ('failure', 'cancelled')
    no_attempt = ci != 'success' and build == deploy == 'skipped'
    deployed = ci == build == deploy == 'success'
    no_promotion = ci == build == 'success' and deploy == 'skipped' and promotion != 'true'
    assert result.returncode == (0 if not actual_failure and (no_attempt or deployed or no_promotion) else 1)
    assert ('Pilot deployment job succeeded' in result.stdout) == deployed
    assert ('No delivery attempted' in result.stdout) == no_attempt
    if no_promotion:
        assert 'Images published; pilot not deployed' in result.stdout
    if actual_failure:
        assert 'no successful deployment is claimed' in result.stdout
        assert 'partially published' in result.stdout


@pytest.mark.parametrize('field', ['ci', 'build', 'deploy', 'promotion', 'sha'])
def test_context_values_are_data_not_shell(tmp_path, field):
    values = dict(ci='success', build='success', deploy='success', promotion='true', sha='a' * 40)
    values[field] = '$(touch injected); `touch injected`; "quoted"'
    run_report(tmp_path, **values)
    assert not (tmp_path / 'injected').exists()


def test_shell_syntax():
    subprocess.run(['bash', '-n'], input=SCRIPT, text=True, check=True, timeout=5)
