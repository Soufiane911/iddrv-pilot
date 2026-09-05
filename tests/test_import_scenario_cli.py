from __future__ import annotations

import pytest

from ingest import import_scenario


def test_import_scenario_help_is_available(capsys):
    with pytest.raises(SystemExit) as raised:
        import_scenario.main(["--help"])
    assert raised.value.code == 0
    assert "--site-id" in capsys.readouterr().out


def test_import_scenario_delegates_directory_and_site(monkeypatch, capsys):
    calls = []

    def fake_ingest(directory, *, site_id):
        calls.append((directory, site_id))

    monkeypatch.setattr(import_scenario, "ingest_scenario", fake_ingest)
    assert import_scenario.main(["demo", "--site-id", "7"]) == 0
    assert calls == [("demo", 7)]
    assert "site 7" in capsys.readouterr().out


def test_import_scenario_rejects_invalid_site_without_ingestion(monkeypatch):
    called = False

    def fake_ingest(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(import_scenario, "ingest_scenario", fake_ingest)
    with pytest.raises(SystemExit):
        import_scenario.main(["demo", "--site-id", "0"])
    assert called is False
