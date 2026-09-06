import json
from pathlib import Path

import pytest

from ingest.probe import main, probe_file


def test_probe_report_does_not_expose_source_values_or_path(tmp_path: Path, capsys):
    source = tmp_path / "confidential-customer-export.csv"
    source.write_text(
        "Timestamp,Cycle_Time\n"
        "2026-07-10T10:00:00Z,CONFIDENTIAL-VALUE\n",
        encoding="utf-8",
    )

    report = probe_file(source)
    captured = capsys.readouterr()
    serialized = json.dumps(report, ensure_ascii=False)

    assert captured.out == ""
    assert captured.err == ""
    assert report["source"] == {
        "extension": ".csv",
        "size_bytes": source.stat().st_size,
    }
    assert "sample" not in report
    assert "file" not in report
    assert "file_name" not in report
    assert "mapping_file" not in report["mapping"]
    assert "confidential-customer-export" not in serialized
    assert str(tmp_path) not in serialized
    assert "CONFIDENTIAL-VALUE" not in serialized
    assert report["validation"]["invalid_values"] == [
        {"line": 1, "field": "cycle_time_s", "code": "invalid_numeric"}
    ]


def test_probe_cli_error_does_not_expose_missing_path(tmp_path: Path, capsys):
    missing = tmp_path / "confidential-customer-export.csv"

    assert main([str(missing), "--json"]) == 2

    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "error": "FileNotFoundError",
        "message": "probe_failed",
    }
    assert str(missing) not in captured.out


def test_probe_validates_parser_version_and_reports_required_fields(tmp_path: Path, capsys):
    source = tmp_path / "export.csv"
    source.write_text("Cycle_Time\n2.5\n", encoding="utf-8")

    report = probe_file(source)
    assert report["validation"]["missing_required_fields"] == ["time"]

    with pytest.raises(ValueError, match="invalid parser version"):
        probe_file(source, parser_version="/tmp/confidential-version")

    assert main([str(source), "--parser-version", "/tmp/confidential-version", "--json"]) == 2
    captured = capsys.readouterr()
    assert "/tmp/confidential-version" not in captured.out
    assert json.loads(captured.out)["message"] == "probe_failed"
