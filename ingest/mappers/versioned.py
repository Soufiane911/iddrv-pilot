"""Versioned industrial mapping registry.

Mappings are selected by ``site + machine + parser_version``.  A wildcard
mapping is a safe default for the two pilot Arburg controllers; a site- or
machine-specific JSON can be added later without changing parser code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from ..mapper import _normalize_label, build_column_map
except ImportError:  # direct ``python ingest/probe.py`` execution
    from mapper import _normalize_label, build_column_map


REGISTRY_ROOT = Path(__file__).parent / "versions"
DEFAULT_PARSER_VERSION = "arburg-selogica-gestica-v1"
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _selector(value: int | str | None, *, wildcard: bool = True) -> str:
    if value is None or value == "":
        if wildcard:
            return "*"
        raise ValueError("unsafe mapping selector")
    segment = str(value)
    if segment in {".", ".."} or not _SAFE_SEGMENT.fullmatch(segment):
        raise ValueError("unsafe mapping selector")
    return segment


def _candidates(site_id: int | str | None, machine_erp_ref: str | None, parser_version: str):
    site = _selector(site_id)
    machine = _selector(machine_erp_ref)
    version = _selector(parser_version, wildcard=False)
    # Most specific first, then the version's wildcard fallback.
    return (
        REGISTRY_ROOT / f"site-{site}-machine-{machine}-{version}.json",
        REGISTRY_ROOT / f"site-{site}-{version}.json",
        REGISTRY_ROOT / f"machine-{machine}-{version}.json",
        REGISTRY_ROOT / f"{version}.json",
    )


def load_mapping(
    *,
    site_id: int | str | None = None,
    machine_erp_ref: str | None = None,
    parser_version: str = DEFAULT_PARSER_VERSION,
) -> dict[str, Any] | None:
    """Load the immutable mapping metadata selected for a source."""
    registry = REGISTRY_ROOT.resolve()
    for candidate in _candidates(site_id, machine_erp_ref, parser_version):
        resolved = candidate.resolve()
        if not resolved.is_relative_to(registry):
            raise ValueError("unsafe mapping path")
        if candidate.exists():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            payload["mapping_file"] = str(candidate)
            return payload
    return None


def build_versioned_column_map(
    headers: list[str],
    *,
    brand: str = "generic",
    site_id: int | str | None = None,
    machine_erp_ref: str | None = None,
    parser_version: str = DEFAULT_PARSER_VERSION,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    """Build the normal map and apply explicit versioned aliases.

    The base canonical dictionary remains the fallback for all brands.  A
    versioned mapping only overrides aliases for the selected brand and keeps
    unknown source columns visible to the evidence/probe report.
    """
    mapping = load_mapping(
        site_id=site_id,
        machine_erp_ref=machine_erp_ref,
        parser_version=parser_version,
    )
    result = build_column_map(headers, brand=brand)
    if not mapping or mapping.get("brand") != brand:
        return result, mapping

    normalized_headers = {_normalize_label(header): header for header in headers}
    for source_label, spec in mapping.get("aliases", {}).items():
        original = normalized_headers.get(_normalize_label(source_label))
        if original is None:
            continue
        scale = float(spec.get("scale", 1.0))
        result[original] = {
            "canonical": spec.get("canonical"),
            "unit": spec.get("unit"),
            "source_unit": spec.get("source_unit", spec.get("unit")),
            "scale": scale,
            "conversion_applied": scale != 1.0,
            "confidence": float(spec.get("confidence", 1.0)),
            "matched_by": source_label,
            "brand": brand,
            "mapping_version": mapping.get("version", parser_version),
        }
    return result, mapping


__all__ = [
    "DEFAULT_PARSER_VERSION",
    "REGISTRY_ROOT",
    "build_versioned_column_map",
    "load_mapping",
]
