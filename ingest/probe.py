"""Bounded, read-only qualification command for industrial exports."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

_INGEST_DIR = Path(__file__).resolve().parent
if str(_INGEST_DIR) not in sys.path:
    sys.path.insert(0, str(_INGEST_DIR))

try:
    from .loader import _parse_source_datetime
    from .mapper import get_mapping_confidence, map_row
    from .mappers.versioned import DEFAULT_PARSER_VERSION, build_versioned_column_map
    from .profiles import DEFAULT_PROFILE_ROOT, load_profile_registry
    from .structural import (
        ReaderLimits,
        classify_structure,
        fingerprint_inspection,
        inspect_file,
    )
except ImportError:  # direct ``python ingest/probe.py`` compatibility
    from loader import _parse_source_datetime
    from mapper import get_mapping_confidence, map_row
    from mappers.versioned import DEFAULT_PARSER_VERSION, build_versioned_column_map
    from profiles import DEFAULT_PROFILE_ROOT, load_profile_registry
    from structural import ReaderLimits, classify_structure, fingerprint_inspection, inspect_file


NUMERIC_FIELDS = {
    "cycle_time_s", "dosing_time_s", "injection_time_s", "cooling_time_s",
    "cushion_mm", "switchover_pressure_bar", "switchover_position",
    "peak_pressure_bar", "clamp_force_kn", "mold_open_time_s", "good_parts",
    "cycle_counter", "oil_temperature_c", "barrel_temp_zone1_c",
    "barrel_temp_zone2_c", "barrel_temp_zone3_c", "mold_temperature_c",
    "energy_kwh", "erp_available_time_h", "erp_running_time_h", "erp_trs",
    "erp_cycle_time_s", "nb_cycles", "erp_good_parts", "erp_scrap_count",
}
DATE_FIELDS = {"started_at", "ended_at"}
NON_NEGATIVE_FIELDS = {
    "erp_available_time_h", "erp_running_time_h", "erp_cycle_time_s", "nb_cycles",
    "erp_good_parts", "erp_scrap_count",
}
REQUIRED_FIELDS_BY_KIND = {
    "machine_cycle": {"time"},
    "production_order": {"production_order_id", "machine_erp_ref", "started_at"},
}
PARSER_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
UNIT_CONVERSIONS = {
    ("ms", "s"): 0.001,
    ("min", "s"): 60.0,
    ("h", "s"): 3600.0,
    ("psi", "bar"): 0.0689475729,
    ("pa", "bar"): 0.00001,
    ("mpa", "bar"): 10.0,
}


def _normalized_unit(value: Any) -> str:
    normalized = str(value or "").strip().casefold().replace("°", "").replace("³", "3")
    return {"c": "celsius", "degc": "celsius"}.get(normalized, normalized)


def _apply_source_units(inspection, column_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    compatible_ambiguous = {("cm3", "mm_or_cm3"), ("mm", "mm_or_cm3")}
    for index, source_name in enumerate(inspection.columns):
        if index >= len(inspection.units) or not inspection.units[index]:
            continue
        details = column_map.get(source_name)
        if not details or not details.get("canonical"):
            continue
        source_unit = _normalized_unit(inspection.units[index])
        target_unit = _normalized_unit(details.get("unit"))
        if source_unit in {"", "-"}:
            continue
        updated = dict(details)
        updated["source_unit"] = source_unit
        existing_source = _normalized_unit(details.get("source_unit"))
        if details.get("conversion_applied") and source_unit == existing_source:
            updated["unit_compatible"] = True
        elif source_unit == target_unit or (source_unit, target_unit) in compatible_ambiguous:
            # An explicit unit row has precedence over a suffix inferred from
            # the header, including removal of an otherwise inferred scale.
            updated["scale"] = 1.0
            updated["conversion_applied"] = False
            updated["unit_compatible"] = True
        elif (source_unit, target_unit) in UNIT_CONVERSIONS:
            updated["scale"] = UNIT_CONVERSIONS[(source_unit, target_unit)]
            updated["conversion_applied"] = True
            updated["unit_compatible"] = True
        else:
            updated["unit_compatible"] = False
            issues.append({"field": details["canonical"], "code": "incompatible_unit"})
        column_map[source_name] = updated
    return issues


def _normalized_header(value: str) -> str:
    return re.sub(r"[\s_.\-/]+", "", value.casefold())


def _timestamp_headers(headers: list[str]) -> tuple[str | None, str | None, str | None]:
    by_normalized = {_normalized_header(header): header for header in headers}
    direct = next(
        (by_normalized[name] for name in ("timestamp", "datetime", "dateheure", "time", "t007") if name in by_normalized),
        None,
    )
    return direct, by_normalized.get("date"), by_normalized.get("heure")


def _combine_date_time(date_value: Any, time_value: Any) -> str:
    text = str(time_value or "").strip()
    try:
        fraction = float(text.replace(",", "."))
    except ValueError:
        fraction = -1
    if 0 <= fraction < 1:
        seconds = int(round(fraction * 86400)) % 86400
        text = f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
    return f"{date_value or ''} {text}".strip()


def _canonical_rows(inspection, column_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Map only the bounded in-memory sample produced by structural inspection."""
    headers = list(inspection.columns)
    direct_time, date_header, time_header = _timestamp_headers(headers)
    rows: list[dict[str, Any]] = []
    for values in inspection.sample_rows:
        raw = {header: values[index] if index < len(values) else None for index, header in enumerate(headers)}
        canonical = map_row(raw, column_map)
        timestamp = raw.get(direct_time) if direct_time else None
        if direct_time and _normalized_header(direct_time) == "t007" and inspection.reference_date:
            timestamp = f"{inspection.reference_date} {timestamp or ''}".strip()
        if timestamp is None and date_header and time_header:
            timestamp = _combine_date_time(raw.get(date_header), raw.get(time_header))
        parsed = _parse_source_datetime(timestamp) if timestamp is not None else None
        canonical["time"] = parsed.isoformat() if parsed is not None else None
        rows.append(canonical)
    return rows


def _raw_value(row: dict[str, Any], field: str) -> Any:
    value = row.get(field)
    if value is not None:
        return value
    raw = row.get("raw_data") or {}
    return next((raw[key] for key in raw if str(key).lower() == field.lower()), None)


def _invalid_values(
    rows: list[dict[str, Any]], required_fields: set[str],
) -> list[dict[str, Any]]:
    """Describe invalid fields without echoing confidential source values."""
    invalid: list[dict[str, Any]] = []
    for line_no, row in enumerate(rows, start=1):
        for field in sorted(required_fields):
            if not row.get(field):
                code = "missing_timestamp" if field in {"time", "started_at"} else "missing_required_value"
                invalid.append({"line": line_no, "field": field, "code": code})
        for field in DATE_FIELDS:
            value = _raw_value(row, field)
            if value not in (None, "") and _parse_source_datetime(value) is None:
                invalid.append({"line": line_no, "field": field, "code": "invalid_timestamp"})
        for field in NUMERIC_FIELDS:
            value = _raw_value(row, field)
            if value is None or isinstance(value, bool):
                continue
            if isinstance(value, str):
                text = value.strip().replace(",", ".")
                try:
                    value = float(text)
                except ValueError:
                    invalid.append({"line": line_no, "field": field, "code": "invalid_numeric"})
                    continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric):
                invalid.append({"line": line_no, "field": field, "code": "non_finite"})
            elif field in {"cycle_time_s", "dosing_time_s", "injection_time_s", "cooling_time_s"} and numeric < 0:
                invalid.append({"line": line_no, "field": field, "code": "negative_duration"})
            elif field in {"peak_pressure_bar", "switchover_pressure_bar"} and numeric > 50000:
                invalid.append({"line": line_no, "field": field, "code": "pressure_out_of_range"})
            elif field in NON_NEGATIVE_FIELDS and numeric < 0:
                invalid.append({"line": line_no, "field": field, "code": "negative_value"})
            elif field == "erp_trs" and not 0 <= numeric <= 1:
                invalid.append({"line": line_no, "field": field, "code": "ratio_out_of_range"})
    return invalid


def probe_file(
    path: str | Path,
    *,
    site_id: int | str | None = None,
    machine_erp_ref: str | None = None,
    parser_version: str = DEFAULT_PARSER_VERSION,
    profile_root: str | Path = DEFAULT_PROFILE_ROOT,
    limits: ReaderLimits = ReaderLimits(),
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Return a bounded JSON-serializable report without database writes."""
    source = Path(path)
    if not PARSER_VERSION_PATTERN.fullmatch(parser_version):
        raise ValueError("invalid parser version")
    if not source.exists() or not source.is_file():
        raise FileNotFoundError("source file is unavailable")

    inspection = inspect_file(source, limits=limits, sheet_name=sheet_name)
    fingerprint = fingerprint_inspection(inspection)
    classification = classify_structure(inspection)
    profile_match = load_profile_registry(profile_root).match(fingerprint)
    effective_parser_version = profile_match.parser_version or parser_version
    if not PARSER_VERSION_PATTERN.fullmatch(effective_parser_version):
        raise ValueError("invalid matched parser version")
    headers = list(inspection.columns)
    versioned_map, mapping = build_versioned_column_map(
        headers,
        brand=inspection.brand_hint,
        site_id=site_id,
        machine_erp_ref=machine_erp_ref,
        parser_version=effective_parser_version,
    )
    unit_issues = _apply_source_units(inspection, versioned_map)
    rows = _canonical_rows(inspection, versioned_map)
    record_kind = profile_match.record_kind or "machine_cycle"
    required_fields = REQUIRED_FIELDS_BY_KIND.get(record_kind, REQUIRED_FIELDS_BY_KIND["machine_cycle"])
    invalid = _invalid_values(rows, required_fields)

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
                "source_unit": details.get("source_unit"),
                "conversion_applied": details.get("conversion_applied", False),
                "conversion_factor": details.get("scale", 1.0),
                "unit_compatible": details.get("unit_compatible", True),
                "confidence": details.get("confidence", 0),
                "matched_by": details.get("matched_by"),
            })
            if details.get("unit"):
                units.setdefault(canonical, set()).add(details["unit"])
        else:
            unknown.append(source_name)

    mapping_score = get_mapping_confidence(versioned_map)
    row_count = len(rows)
    missing_required_fields = sorted(
        field for field in required_fields if not rows or all(not row.get(field) for row in rows)
    )
    invalid_ratio = len(invalid) / max(1, row_count)
    score = max(0.0, min(1.0, mapping_score * (1.0 - min(0.5, invalid_ratio / 2))))
    return {
        "source": {
            "extension": source.suffix.lower(),
            "size_bytes": source.stat().st_size,
        },
        "read_only": True,
        "writes_database": False,
        "structure": {
            "fingerprint_version": fingerprint.version,
            "fingerprint": fingerprint.digest,
            "format_family": inspection.family,
            "source_format": inspection.source_format,
            "classification": {
                "label": classification.label,
                "score": classification.score,
                "threshold": classification.threshold,
                "signals": classification.signals,
            },
            "profile_match": {
                "status": profile_match.status,
                "profile_id": profile_match.profile_id,
                "profile_version": profile_match.profile_version,
                "parser_version": profile_match.parser_version,
                "record_kind": profile_match.record_kind,
            },
            "bounded": {
                "rows_observed": inspection.rows_observed,
                "max_rows": limits.max_sample_rows,
                "truncated": inspection.truncated,
            },
            "sheet": {
                "name": inspection.sheet_name,
                "index": inspection.sheet_index,
                "count": inspection.sheet_count,
            } if inspection.family == "spreadsheet" else None,
        },
        "profile": {
            "brand": inspection.brand_hint,
            "brand_confidence": inspection.brand_confidence,
            "encoding": inspection.encoding,
            "encoding_confidence": None,
            "delimiter": inspection.delimiter,
            "is_transposed": inspection.orientation == "transposed",
            "header_row": inspection.header_row,
            "unit_row": inspection.unit_row,
            "data_start_row": inspection.data_start_row,
            "rows": row_count,
            "columns": len(headers),
            "notes": ["binary_format_requires_dedicated_adapter"] if inspection.family == "binary" else [],
        },
        "mapping": {
            "parser_version": effective_parser_version,
            "requested_parser_version": parser_version,
            "selected_version": mapping.get("version") if mapping else None,
            "recognized_columns": recognized,
            "unknown_columns": unknown,
            "units": {name: sorted(values) for name, values in units.items()},
            "confidence": round(score, 3),
        },
        "validation": {
            "scope": "sample" if inspection.truncated else "complete",
            "complete": not inspection.truncated,
            "missing_required_fields": missing_required_fields,
            "unit_issues": unit_issues,
            "invalid_values": invalid,
            "invalid_count": len(invalid),
            "rows_with_invalid_values": len({item["line"] for item in invalid}),
            "valid": not invalid and not unit_issues and bool(rows) and inspection.family != "binary",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe an industrial file without database insertion")
    parser.add_argument("file", type=Path)
    parser.add_argument("--site-id")
    parser.add_argument("--machine-erp-ref")
    parser.add_argument("--parser-version", default=DEFAULT_PARSER_VERSION)
    parser.add_argument("--sheet-name")
    parser.add_argument("--json", action="store_true", help="emit compact JSON")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        result = probe_file(
            args.file,
            site_id=args.site_id,
            machine_erp_ref=args.machine_erp_ref,
            parser_version=args.parser_version,
            sheet_name=args.sheet_name,
        )
    except Exception as exc:
        error = getattr(exc, "code", type(exc).__name__)
        print(json.dumps({"error": error, "message": "probe_failed"}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str, indent=None if args.json else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
