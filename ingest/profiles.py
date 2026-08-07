"""Read-only registry for versioned structural import profiles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

try:
    from .structural import FINGERPRINT_VERSION, StructuralError, StructuralFingerprint
except ImportError:  # direct script compatibility
    from structural import FINGERPRINT_VERSION, StructuralError, StructuralFingerprint


DEFAULT_PROFILE_ROOT = Path(__file__).parent / "profiles"
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class ProfileMatch:
    status: Literal["approved", "candidate", "none"]
    profile_id: str | None
    profile_version: str | None
    parser_version: str | None
    record_kind: str | None


@dataclass(frozen=True)
class ProfileRegistry:
    profiles: tuple[dict[str, Any], ...]

    def match(self, fingerprint: StructuralFingerprint) -> ProfileMatch:
        matches = [
            profile for profile in self.profiles
            if profile.get("match_enabled", True)
            and profile.get("fingerprint", {}).get("digest") == fingerprint.digest
            and profile.get("fingerprint", {}).get("version") == fingerprint.version
        ]
        approved = [profile for profile in matches if profile["status"] == "approved"]
        candidates = [profile for profile in matches if profile["status"] == "candidate"]
        if len(approved) > 1 or (not approved and len(candidates) > 1):
            raise StructuralError("INGEST_PROFILE_DUPLICATE", "multiple profiles match the structure")
        selected = approved[0] if approved else (candidates[0] if candidates else None)
        if selected is None:
            return ProfileMatch("none", None, None, None, None)
        return ProfileMatch(
            selected["status"], selected["profile_id"], selected["profile_version"],
            selected.get("mapping", {}).get("parser_version"),
            selected.get("qualification", {}).get("record_kind"),
        )


def _validate_profile(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"schema", "schema_version", "profile_id", "profile_version", "status"}
    if not required.issubset(payload):
        raise StructuralError("INGEST_PROFILE_INVALID", "structural profile is incomplete")
    if payload["schema"] != "iddrv.structural-profile" or payload["schema_version"] != 1:
        raise StructuralError("INGEST_PROFILE_INVALID", "structural profile schema is unsupported")
    if payload["status"] not in {"approved", "candidate"}:
        raise StructuralError("INGEST_PROFILE_INVALID", "structural profile status is invalid")
    if payload["status"] == "approved":
        approval = payload.get("approval", {})
        qualification = payload.get("qualification", {})
        if not approval.get("approved_at") or not approval.get("approved_by") or qualification.get("field_validated") is not True:
            raise StructuralError("INGEST_PROFILE_INVALID", "approved profile lacks field-validation evidence")
    if not IDENTIFIER_PATTERN.fullmatch(str(payload["profile_id"])):
        raise StructuralError("INGEST_PROFILE_INVALID", "structural profile identifier is invalid")
    if not IDENTIFIER_PATTERN.fullmatch(str(payload["profile_version"])):
        raise StructuralError("INGEST_PROFILE_INVALID", "structural profile version is invalid")
    parser_version = payload.get("mapping", {}).get("parser_version")
    if parser_version is not None and not IDENTIFIER_PATTERN.fullmatch(str(parser_version)):
        raise StructuralError("INGEST_PROFILE_INVALID", "mapping parser version is invalid")

    enabled = payload.get("match_enabled", True)
    fingerprint = payload.get("fingerprint")
    if enabled:
        if not isinstance(fingerprint, dict):
            raise StructuralError("INGEST_PROFILE_INVALID", "enabled profile requires a fingerprint")
        if fingerprint.get("version") != FINGERPRINT_VERSION:
            raise StructuralError("INGEST_PROFILE_INVALID", "profile fingerprint version is unsupported")
        if not DIGEST_PATTERN.fullmatch(str(fingerprint.get("digest", ""))):
            raise StructuralError("INGEST_PROFILE_INVALID", "profile fingerprint digest is invalid")
    return payload


def load_profile_registry(root: str | Path = DEFAULT_PROFILE_ROOT) -> ProfileRegistry:
    directory = Path(root)
    if not directory.exists():
        return ProfileRegistry(())
    profiles: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for path in sorted(directory.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StructuralError("INGEST_PROFILE_INVALID", "structural profile cannot be read") from exc
        profile = _validate_profile(payload)
        identifier = profile["profile_id"]
        if identifier in identifiers:
            raise StructuralError("INGEST_PROFILE_DUPLICATE", "structural profile identifier is duplicated")
        identifiers.add(identifier)
        profiles.append(profile)
    return ProfileRegistry(tuple(profiles))


def make_candidate_profile(
    fingerprint: StructuralFingerprint, *, profile_id: str, parser_version: str,
) -> dict[str, Any]:
    payload = {
        "schema": "iddrv.structural-profile",
        "schema_version": 1,
        "profile_id": profile_id,
        "profile_version": "1.0.0",
        "status": "candidate",
        "match_enabled": True,
        "fingerprint": {"version": fingerprint.version, "digest": fingerprint.digest},
        "mapping": {"parser_version": parser_version},
        "approval": {"approved_at": None, "approved_by": None},
    }
    return _validate_profile(payload)


__all__ = [
    "DEFAULT_PROFILE_ROOT", "ProfileMatch", "ProfileRegistry", "load_profile_registry",
    "make_candidate_profile",
]
