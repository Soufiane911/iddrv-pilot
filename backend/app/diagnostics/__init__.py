"""Deterministic, evidence-first production diagnostics.

The package deliberately has no LLM dependency.  An API adapter can provide a
repository implementing :class:`DiagnosticRepository` and serialize the
returned dataclasses to the v1 contract.
"""

from .engine import DiagnosticEngine, DeterministicInvestigator, Investigator
from .models import Investigation, InsufficientDataError
from .repository import DiagnosticRepository, InMemoryDiagnosticRepository

__all__ = [
    "DiagnosticEngine",
    "DeterministicInvestigator",
    "Investigator",
    "DiagnosticRepository",
    "InMemoryDiagnosticRepository",
    "Investigation",
    "InsufficientDataError",
]
