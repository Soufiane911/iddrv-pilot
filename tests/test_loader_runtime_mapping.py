from datetime import datetime, timezone

from ingest.ingest_pipeline import _source_datetime
from ingest.loader import load_file
from ingest.profiler import FileProfile


def test_erp_and_context_naive_timestamp_use_site_timezone():
    parsed = _source_datetime("2026-07-10 08:00:00", "Europe/Paris")
    assert parsed is not None
    assert parsed.hour == 6
    assert parsed.tzinfo == timezone.utc


def test_generic_naive_timestamp_uses_site_timezone(tmp_path):
    source = tmp_path / "generic.csv"
    source.write_text(
        "Timestamp,Cycle_Time\n2026-07-10 08:00:00,10\n",
        encoding="utf-8",
    )

    rows, _, _ = load_file(str(source), source_timezone="Europe/Paris")

    parsed = datetime.fromisoformat(rows[0]["time"])
    assert parsed.astimezone(timezone.utc).hour == 6


def test_runtime_loader_uses_versioned_mapping_and_site_timezone(tmp_path, monkeypatch):
    source = tmp_path / "arburg.txt"
    source.write_text(
        "t007;t4012;p4072\n"
        "08:00:00;10;100\n",
        encoding="utf-8",
    )
    profile = FileProfile(
        file_path=str(source),
        encoding="utf-8",
        delimiter=";",
        brand_detected="arburg",
        header_row_index=0,
        data_start_row=1,
        metadata_lines=["Date: 2026-07-10"],
    )
    monkeypatch.setattr("ingest.loader.profile_file", lambda _: profile)

    rows, _, mapping = load_file(
        str(source),
        site_id=1,
        machine_erp_ref="1003",
        source_timezone="Europe/Paris",
    )

    assert mapping["p4072"]["mapping_version"] == "arburg-selogica-gestica-v1"
    parsed = datetime.fromisoformat(rows[0]["time"])
    assert parsed.tzinfo is not None
    assert parsed.astimezone(timezone.utc).hour == 6
