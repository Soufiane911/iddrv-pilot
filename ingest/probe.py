"""Read-only format qualification command for industrial exports.

``probe`` profiles and maps a file, but never opens PostgreSQL, creates an
import passport, or calls a business importer.  It is intentionally useful on
an engineer laptop before a real Arburg Selogica/Gestica export is accepted.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

# The existing ingestion modules predate package execution and import
# ``profiler``/``mapper`` as top-level modules.  Keep ``python ingest/*.py``
# compatibility while making ``python -m ingest.probe`` work from the repo
# root.
_INGEST_DIR = Path(__file__).resolve().parent
if str(_INGEST_DIR) not in sys.path:
    sys.path.insert(0, str(_INGEST_DIR))

try:
    from .loader import load_file, read_arburg_protocol, read_transposed_file
    from .mapper import get_mapping_confidence
    from .mappers.versioned import DEFAULT_PARSER_VERSION, build_versioned_column_map
    from .profiler import profile_file
except ImportError:  # ``python ingest/probe.py ...`` compatibility
    from loader import load_file, read_arburg_protocol, read_transposed_file
    from mapper import get_mapping_confidence
    from mappers.versioned import DEFAULT_PARSER_VERSION, build_versioned_column_map
    from profiler import profile_file


NUMERIC_FIELDS = {
    "cycle_time_s", "dosing_time_s", "injection_time_s", "cooling_time_s",
    "cushion_mm", "switchover_pressure_bar", "switchover_position",
    "peak_pressure_bar", "clamp_force_kn", "mold_open_time_s", "good_parts",
    "cycle_counter", "oil_temperature_c", "barrel_temp_zone1_c",
    "barrel_temp_zone2_c", "barrel_temp_zone3_c", "mold_temperature_c",
    "energy_kwh",
}
REQUIRED_FIELDS = {"time"}


def _headers_and_rows(path: Path, profile):
    """Read via existing pure loaders and expose headers for the report."""
    if profile.is_transposed:
        rows, col_map = read_transposed_file(profile)
        return list(col_map), rows, col_map
    if profile.brand_detected == "arburg" or profile.metadata_lines:
        rows, col_map = read_arburg_protocol(profile)
        return list(col_map), rows, col_map
    rows, _, col_map = load_file(str(path))
    return list(col_map), rows, col_map


def _raw_value(row: dict[str, Any], field: str) -> Any:
    value = row.get(field)
    if value is not None:
        return value
    raw = row.get("raw_data") or {}
    return next((raw[key] for key in raw if str(key).lower() == field.lower()), None)


def _invalid_values(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    invalid: list[dict[str, Any]] = []
    for line_no, row in enumerate(rows, start=1):
        if not row.get("time"):
            invalid.append({"line": line_no, "field": "time", "code": "missing_timestamp", "value": None})
        for field in NUMERIC_FIELDS:
            value = _raw_value(row, field)
            if value is None or isinstance(value, bool):
                continue
            if isinstance(value, str):
                text = value.strip().replace(",", ".")
                try:
                    value = float(text)
                except ValueError:
                    invalid.append({"line": line_no, "field": field, "code": "invalid_numeric", "value": value})
                    continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric):
                invalid.append({"line": line_no, "field": field, "code": "non_finite", "value": str(value)})
            elif field in {"cycle_time_s", "dosing_time_s", "injection_time_s", "cooling_time_s"} and numeric < 0:
                invalid.append({"line": line_no, "field": field, "code": "negative_duration", "value": numeric})
            elif field in {"peak_pressure_bar", "switchover_pressure_bar"} and numeric > 50000:
                invalid.append({"line": line_no, "field": field, "code": "pressure_out_of_range", "value": numeric})
    return invalid


def probe_file(
    path: str | Path,
    *,
    site_id: int | str | None = None,
    machine_erp_ref: str | None = None,
    parser_version: str = DEFAULT_PARSER_VERSION,
) -> dict[str, Any]:
    """Return a JSON-serializable, insertion-free qualification report."""
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(str(source))
    profile = profile_file(str(source))
    headers, rows, base_map = _headers_and_rows(source, profile)
    versioned_map, mapping = build_versioned_column_map(
        headers,
        brand=profile.brand_detected,
        site_id=site_id,
        machine_erp_ref=machine_erp_ref,
        parser_version=parser_version,
    )
    invalid = _invalid_values(rows)
    recognized = []
    unknown = []
    units: dict[str, set[str]] = {}
    for source_name, details in versioned_map.items():
        canonical = details.get("canonical")
        if canonical:
            recognized.append({
                "source": source_name,
                "canonical": canonical,
                "unit": details.get("unit"),
                "confidence": details.get("confidence", 0),
                "matched_by": details.get("matched_by"),
            })
            if details.get("unit"):
                units.setdefault(canonical, set()).add(details["unit"])
        else:
            unknown.append(source_name)

    mapping_score = get_mapping_confidence(versioned_map)
    row_count = len(rows)
    invalid_ratio = len(invalid) / max(1, row_count)
    # Invalid rows reduce trust but never hide the raw/unknown columns.
    score = max(0.0, min(1.0, mapping_score * (1.0 - min(0.5, invalid_ratio / 2))))
    return {
        "file": str(source),
        "file_name": source.name,
        "read_only": True,
        "writes_database": False,
        "profile": {
            "brand": profile.brand_detected,
            "brand_confidence": profile.brand_confidence,
            "encoding": profile.encoding,
            "encoding_confidence": profile.encoding_confidence,
            "delimiter": profile.delimiter,
            "is_transposed": profile.is_transposed,
            "header_row": profile.header_row_index,
            "unit_row": profile.unit_row_index,
            "data_start_row": profile.data_start_row,
            "rows": row_count,
            "columns": len(headers),
            "notes": list(profile.notes),
        },
        "mapping": {
            "parser_version": parser_version,
            "selected_version": mapping.get("version") if mapping else None,
            "mapping_file": mapping.get("mapping_file") if mapping else None,
            "recognized_columns": recognized,
            "unknown_columns": unknown,
            "units": {name: sorted(values) for name, values in units.items()},
            "confidence": round(score, 3),
        },
        "validation": {
            "invalid_values": invalid,
            "invalid_count": len(invalid),
            "rows_with_invalid_values": len({item["line"] for item in invalid}),
            "valid": not invalid and bool(rows),
        },
        "sample": rows[:3],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe an industrial file without database insertion")
    parser.add_argument("file", type=Path)
    parser.add_argument("--site-id")
    parser.add_argument("--machine-erp-ref")
    parser.add_argument("--parser-version", default=DEFAULT_PARSER_VERSION)
    parser.add_argument("--json", action="store_true", help="emit compact JSON (default is JSON too, kept for explicit scripts)")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        result = probe_file(
            args.file,
            site_id=args.site_id,
            machine_erp_ref=args.machine_erp_ref,
            parser_version=args.parser_version,
        )
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str, indent=None if args.json else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
