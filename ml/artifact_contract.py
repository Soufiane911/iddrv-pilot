"""Shared safety checks for serialized ML artifacts.

Joblib artifacts contain executable Python objects and sklearn records the
training version in estimator state.  Loading an artifact from another sklearn
release can silently change predictions, so compatibility is checked before a
model is handed to an endpoint.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import warnings
from typing import Any

import joblib
import sklearn
from sklearn.exceptions import InconsistentVersionWarning

SUPPORTED_SKLEARN_VERSION = "1.7.2"
SUPPORTED_JOBLIB_VERSION = "1.5.2"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ArtifactContractError(ValueError):
    """An artifact is missing or violates the serving/runtime contract."""


def runtime_environment() -> dict[str, str]:
    """Return the exact dependency versions supported by the serving runtime."""

    return {
        "python": platform.python_version(),
        "scikit_learn": str(sklearn.__version__),
        "joblib": str(joblib.__version__),
    }


def model_path_from_env(environment_name: str, default_filename: str) -> Path:
    """Resolve model paths independently of the process working directory.

    Checked-in defaults are rooted at the repository.  An explicitly
    configured path keeps the conventional process-relative semantics, while
    deployments can provide an absolute mounted path through the environment.
    """

    configured = os.getenv(environment_name, "").strip()
    if configured:
        return Path(configured).expanduser()
    return PROJECT_ROOT / "models" / default_filename


def _version_mismatch_message(path: Path, warning_message: str) -> str:
    return (
        f"Incompatible sklearn version recorded in model artifact {path}: "
        f"{warning_message}. Runtime supports scikit-learn=={SUPPORTED_SKLEARN_VERSION}."
    )


def load_serialized_artifact(path: Path) -> dict[str, Any]:
    """Load a dict artifact while turning sklearn mismatch warnings into errors.

    Only ``InconsistentVersionWarning`` is intercepted.  Other warnings remain
    visible to callers, so deprecations and operational problems are not
    accidentally hidden by the compatibility guard.
    """

    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        # Restrict the temporary filter to the critical compatibility warning.
        # Other warnings retain the caller's policy and are never swallowed.
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            artifact = joblib.load(path)
    except InconsistentVersionWarning as exc:
        raise ArtifactContractError(_version_mismatch_message(path, str(exc))) from exc
    if not isinstance(artifact, dict):
        raise ArtifactContractError(f"ML artifact must be a dictionary: {path}")
    metadata = _read_sidecar(path)
    if isinstance(artifact.get("environment"), dict):
        validate_environment(artifact, path)
    elif metadata is not None and isinstance(metadata.get("environment"), dict):
        # Artifacts produced before provenance was embedded remain loadable only
        # when their checked-in sibling metadata supplies the same evidence.
        validate_environment({"environment": metadata["environment"]}, path)
    else:
        raise ArtifactContractError(f"ML artifact provenance is missing: {path}")
    _validate_sidecar(path, artifact, metadata)
    return artifact


def _read_sidecar(path: Path) -> dict[str, Any] | None:
    metadata_path = path.with_suffix(".meta.json")
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactContractError(f"ML artifact metadata is unreadable: {metadata_path}") from exc
    if not isinstance(metadata, dict):
        raise ArtifactContractError(f"ML artifact metadata is invalid: {metadata_path}")
    return metadata


def _validate_sidecar(path: Path, artifact: dict[str, Any], metadata: dict[str, Any] | None) -> None:
    """Reject a stale or tampered sibling metadata file when one is present."""

    if metadata is None:
        return
    metadata_path = path.with_suffix(".meta.json")
    for key in ("model_version", "feature_columns"):
        if metadata.get(key) != artifact.get(key):
            raise ArtifactContractError(f"ML artifact metadata does not match artifact: {metadata_path}")
    if isinstance(artifact.get("environment"), dict) and metadata.get("environment") != artifact["environment"]:
        raise ArtifactContractError(f"ML artifact metadata does not match artifact: {metadata_path}")


def validate_environment(artifact: dict[str, Any], path: Path | str = "artifact") -> None:
    """Require provenance embedded at training time and exact runtime versions."""

    environment = artifact.get("environment")
    if not isinstance(environment, dict):
        raise ArtifactContractError(f"ML artifact provenance is missing: {path}")
    expected = runtime_environment()
    supported = {"scikit_learn": SUPPORTED_SKLEARN_VERSION, "joblib": SUPPORTED_JOBLIB_VERSION}
    for key, supported_version in supported.items():
        if expected[key] != supported_version:
            raise ArtifactContractError(
                f"Runtime {key} version {expected[key]} is unsupported; "
                f"expected {key}=={supported_version}"
            )
        actual = str(environment.get(key, ""))
        if actual != expected[key]:
            raise ArtifactContractError(
                f"ML artifact {key} version {actual or 'unknown'} is incompatible; "
                f"runtime requires {key}=={expected[key]}"
            )
    actual_python = str(environment.get("python", ""))
    expected_python = expected["python"]
    if ".".join(actual_python.split(".")[:2]) != ".".join(expected_python.split(".")[:2]):
        raise ArtifactContractError(
            f"ML artifact Python version {actual_python or 'unknown'} is incompatible; "
            f"runtime requires Python {'.'.join(expected_python.split('.')[:2])}"
        )
