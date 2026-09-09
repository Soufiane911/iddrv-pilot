import os
from dataclasses import replace

import pytest


@pytest.fixture
def summary6_data(tmp_path, monkeypatch):
    from summary6_factory import demo_catalog
    from backend.app.services import summary6 as service
    folder = tmp_path / 'summary6-generated'
    pin = demo_catalog(folder)
    monkeypatch.setattr(service, 'DATA', folder)
    monkeypatch.setattr(service, 'MANIFEST_SHA', pin)
    return folder


@pytest.fixture(scope='session')
def training_data(tmp_path_factory):
    from scripts.generate_training_fixture import generate
    return generate(tmp_path_factory.mktemp('training') / 'cycles')


@pytest.fixture(scope='session')
def sample_data(tmp_path_factory):
    import random
    from ingest import generate_samples as generator
    folder = tmp_path_factory.mktemp('generated-samples')
    state = random.getstate()
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(generator, 'OUTPUT_DIR', folder)
            random.seed(719)
            generator.generate_arburg_protocol(n_cycles=12)
            generator.generate_engel_csv(n_cycles=12)
            generator.generate_transposed_tubes(n_cycles=32)
            generator.generate_erp_trs_xlsx()
    finally:
        random.setstate(state)
    return folder


@pytest.fixture(autouse=True)
def _test_session_fail_open(monkeypatch):
    monkeypatch.setenv("SESSION_FAIL_OPEN", "true")
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    monkeypatch.setenv("METRICS_PUBLIC", "true")
    monkeypatch.setattr("backend.app.auth_repository.session_is_active", lambda identity, token: True)
    from backend.app import config, metrics, security

    test_settings = replace(
        security.settings,
        app_environment="test",
        allow_anonymous_reads=True,
        metrics_token="",
        metrics_public=True,
    )
    monkeypatch.setattr(security, "settings", test_settings)
    monkeypatch.setattr(config, "settings", test_settings)
    monkeypatch.setattr(metrics, "settings", test_settings)
