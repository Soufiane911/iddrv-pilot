"""Read-only release catalogue. Never imports research code or loads artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CATALOG_PATH = Path(__file__).resolve().parents[1] / "models/hdt/catalog.json"
HISTORICAL_ID = "hdt-historical-v1-release-29dea3dca96a"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Record):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def safe_reference(self):
        # References are identifiers only, never passed to a filesystem loader.
        if not re.fullmatch(r"(?:models|output)/[A-Za-z0-9_./-]+", self.path) or any(
            part in ("", ".", "..") for part in self.path.split("/")
        ):
            raise ValueError("unsafe provenance reference")
        return self


class Artifact(Evidence):
    artifact_packaged: bool
    distribution: Literal["packaged", "source_only"]
    dataset: str
    seed: int | None

    @model_validator(mode="after")
    def distribution_matches(self):
        if self.artifact_packaged != (self.distribution == "packaged"):
            raise ValueError("inconsistent artifact distribution")
        return self


class Evaluation(Record):
    phase: Literal["confirmation", "development"]
    population: str
    dataset_ids: list[int]
    seeds: list[int]
    useful_recall_pct: float = Field(ge=0, le=100)
    episode_recall_pct: float | None = Field(default=None, ge=0, le=100)
    fp_per_1000_healthy_cycles: float = Field(ge=0)
    support_pct: float = Field(ge=0, le=100)
    distinct_episodes: int | None = Field(default=None, ge=0)
    interpretation: str


class InputContract(Record):
    sensors: list[str]
    context: list[str]
    preprocessing: str
    decision: str
    runtime_compatible: bool


class Candidate(Record):
    candidate_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]+$")
    label: str
    representation: str
    model_version: str
    default: bool
    status: Literal["executable", "research_only", "blocked"]
    scientific_status: str
    blocked_reason: str | None
    artifact: Artifact
    evidence: list[Evidence] = Field(min_length=1)
    input_contract: InputContract
    evaluations: list[Evaluation]

    @model_validator(mode="after")
    def execution_boundary(self):
        if not self.candidate_id.endswith(self.artifact.sha256[:12]):
            raise ValueError("candidate identity must bind artifact fingerprint")
        executable = self.status == "executable"
        if executable != self.default or (executable and self.candidate_id != HISTORICAL_ID):
            raise ValueError("only historical default is executable in catalogue v1")
        if executable and (not self.artifact.artifact_packaged or not self.input_contract.runtime_compatible or self.blocked_reason):
            raise ValueError("invalid executable contract")
        if not executable and (not self.blocked_reason or self.artifact.artifact_packaged or self.input_contract.runtime_compatible):
            raise ValueError("research must remain source-only and blocked")
        return self


class Catalog(Record):
    schema_version: Literal[1]
    notice: str
    candidates: list[Candidate]

    @model_validator(mode="after")
    def unique_default(self):
        if sum(c.default for c in self.candidates) != 1:
            raise ValueError("exactly one default required")
        if len({c.candidate_id for c in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate candidate id")
        return self


def load_catalog() -> Catalog:
    """Fixed versioned JSON only; no user path, env override or artifact I/O."""
    return Catalog.model_validate(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
