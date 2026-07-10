"""Deterministic, evidence-first investigations.

The pilot deliberately keeps diagnosis local and reproducible.  This module
does not know about scenario files, prompts or an LLM: it receives bounded
rows through :class:`~backend.app.diagnostics.repository.DiagnosticRepository`
and returns a small ranked set of hypotheses with traceable evidence.

``DiagnosticEngine`` is retained as the backwards-compatible S001 entrypoint
used by the API.  New callers should depend on the ``Investigator`` protocol
and instantiate ``DeterministicInvestigator``; the latter enables conservative
minimum-sample abstention by default.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import mean, median, pstdev
from typing import Protocol, runtime_checkable
from uuid import NAMESPACE_URL, uuid5

from .models import Evidence, Hypothesis, InsufficientDataError, Investigation
from .repository import DiagnosticRepository, Row


UTC = timezone.utc


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _num(row: Mapping, *keys: str) -> float | None:
    """Read a finite numeric value, tolerating CSV/DB string values."""

    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(parsed):
            return parsed
    return None


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "scrap", "reject"}


def _scrap(row: Mapping) -> bool:
    return _bool(row.get("scrap_flag")) or str(row.get("part_quality_status", "")).lower() in {
        "scrap",
        "reject",
        "non_conforme",
        "non-conforme",
    }


def _timestamp(row: Mapping) -> datetime | None:
    value = row.get("timestamp", row.get("time"))
    if value is None:
        return None
    try:
        return _dt(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _values(rows: Iterable[Row], *keys: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = _num(row, *keys)
        if value is not None:
            values.append(value)
    return values


def _safe_mean(values: Sequence[float]) -> float | None:
    return mean(values) if values else None


def _safe_median(values: Sequence[float]) -> float | None:
    return median(values) if values else None


def _safe_stdev(values: Sequence[float]) -> float | None:
    # A single observation has no useful instability signal.
    return pstdev(values) if len(values) >= 2 else None


def _split_defects(value) -> list[str]:
    if value is None:
        return []
    text = str(value).strip().lower()
    if not text:
        return []
    for separator in (";", "|", ","):
        text = text.replace(separator, " ")
    return [token for token in text.split() if token and token not in {"good", "valid", "none"}]


def _defects(rows: Iterable[Row]) -> Counter[str]:
    result: Counter[str] = Counter()
    for row in rows:
        values = _split_defects(row.get("defect_type"))
        if not values:
            values = _split_defects(row.get("quality_flag"))
        for value in values:
            result[value] += int(_num(row, "defect_count") or 1)
    return result


def _order_tokens(value) -> set[str]:
    """Handle an OF id and the ``OF-a to OF-z`` S006 notation."""

    if not value:
        return set()
    text = str(value)
    if " to " in text:
        start, end = text.split(" to ", 1)
        return {start.strip(), end.strip()}
    return {text.strip()}


def _related(rows: Iterable[Row], production_order_id) -> list[Row]:
    order_ids = _order_tokens(production_order_id)
    rows = list(rows)
    if not order_ids:
        return rows
    linked: list[Row] = []
    for row in rows:
        row_order = str(row.get("production_order_id") or "").strip()
        # Blank order on a maintenance event is intentionally machine-level
        # context and remains relevant to the incident.
        if not row_order or row_order in order_ids:
            linked.append(row)
    return linked


def _trend(rows: Iterable[Row], value_key: str) -> tuple[float | None, float | None, int]:
    """Return slope per day, first/last median delta and sample count."""

    points = []
    for row in rows:
        timestamp = _timestamp(row)
        value = _num(row, value_key)
        if timestamp is not None and value is not None:
            points.append((timestamp, value))
    points.sort(key=lambda item: item[0])
    if len(points) < 3:
        return None, None, len(points)
    first = [value for _, value in points[: max(1, len(points) // 4)]]
    last = [value for _, value in points[-max(1, len(points) // 4) :]]
    x0 = points[0][0]
    xs = [(timestamp - x0).total_seconds() / 86400 for timestamp, _ in points]
    ys = [value for _, value in points]
    x_bar, y_bar = mean(xs), mean(ys)
    denominator = sum((x - x_bar) ** 2 for x in xs)
    slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys)) / denominator if denominator else None
    return slope, median(last) - median(first), len(points)


@runtime_checkable
class Investigator(Protocol):
    """Stable dependency boundary for API, evaluation and future providers."""

    def investigate(self, **kwargs) -> Investigation: ...


class DeterministicInvestigator:
    """Rank evidence-backed hypotheses for the six pilot failure patterns.

    The scoring is intentionally transparent.  A candidate only receives
    support from rows retrieved for the requested machine and time window;
    every hypothesis points to one or more evidence ids.  When conservative
    mode is active, sparse windows abstain rather than manufacture a causal
    conclusion.
    """

    _MIN_EVENT_CYCLES = 3
    _MIN_QUALITY_CHECKS = 2

    def __init__(
        self,
        repository: DiagnosticRepository,
        *,
        baseline_multiplier: float = 1.0,
        minimum_event_cycles: int = _MIN_EVENT_CYCLES,
        minimum_quality_checks: int = _MIN_QUALITY_CHECKS,
        abstain_on_insufficient: bool = True,
    ):
        self.repository = repository
        self.baseline_multiplier = baseline_multiplier
        self.minimum_event_cycles = max(1, minimum_event_cycles)
        self.minimum_quality_checks = max(1, minimum_quality_checks)
        self.abstain_on_insufficient = abstain_on_insufficient

    @staticmethod
    def _evidence_id(source_ref: str, metric: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"iddrv:evidence:{source_ref}:{metric}"))

    def _evidence(
        self,
        evidence: list[Evidence],
        *,
        source_kind: str,
        source_ref: str,
        metric: str,
        start: datetime,
        end: datetime,
        observation: dict,
        baseline: dict | None = None,
        delta: float | None = None,
        supports: bool = True,
        excerpt: str | None = None,
    ) -> Evidence:
        item = Evidence(
            self._evidence_id(source_ref, metric),
            source_kind,
            source_ref,
            metric,
            {"start": start.isoformat(), "end": end.isoformat()},
            observation,
            baseline,
            delta,
            supports,
            excerpt,
        )
        # Evidence can be shared by two candidate hypotheses (for example a
        # scrap-rate aggregate).  Keep one stable object per id for persistence.
        if not any(existing.id == item.id for existing in evidence):
            evidence.append(item)
        return next(existing for existing in evidence if existing.id == item.id)

    @staticmethod
    def _supports_defect(defect_counts: Counter[str], expected: set[str]) -> bool:
        return bool(expected.intersection(defect_counts))

    @staticmethod
    def _candidate_confidence(score: float, support_count: int, missing: list[str]) -> float:
        # Score is unbounded internally; this calibration keeps confidence
        # conservative and makes missing baselines visible to the client.
        value = min(0.97, 0.36 + 0.075 * min(score, 7) + 0.04 * min(support_count, 4))
        if missing:
            value = min(value, 0.62)
        return round(value, 4)

    def investigate(
        self,
        *,
        machine_id,
        machine_erp_ref=None,
        production_order_id,
        started_at,
        ended_at,
        defect_type="short_shot",
        incident_id=None,
    ) -> Investigation:
        start, end = _dt(started_at), _dt(ended_at)
        if end < start:
            raise InsufficientDataError("Incident end precedes its start")
        duration = max(end - start, timedelta(minutes=1))
        baseline_start, baseline_end = start - duration * self.baseline_multiplier, start

        event_cycles = list(self.repository.cycles(machine_id, start, end))
        baseline_cycles = list(self.repository.cycles(machine_id, baseline_start, baseline_end))
        quality = list(self.repository.quality_checks(machine_id, start, end))
        context_start, context_end = start - timedelta(hours=6), end + timedelta(hours=6)
        notes = _related(self.repository.operator_notes(machine_id, context_start, context_end), production_order_id)
        maintenance = _related(
            self.repository.maintenance_events(machine_id, context_start, context_end), production_order_id
        )

        if not event_cycles and not quality:
            raise InsufficientDataError("No cycle or quality data exists in the incident window")

        missing: list[str] = []
        if len(event_cycles) < self.minimum_event_cycles:
            missing.append("event_cycles")
        if len(quality) < self.minimum_quality_checks:
            missing.append("quality_checks")
        if not baseline_cycles:
            missing.append("baseline_cycles")
        # The legacy S001 tests intentionally exercise one-cycle windows and
        # expect a low-confidence result.  Conservative callers use the new
        # DeterministicInvestigator default and receive a hard abstention.
        if self.abstain_on_insufficient and len(event_cycles) < self.minimum_event_cycles and len(quality) < self.minimum_quality_checks:
            raise InsufficientDataError(
                f"Insufficient samples: {len(event_cycles)} cycles and {len(quality)} quality checks"
            )

        evidence: list[Evidence] = []
        defect_counts = _defects([*event_cycles, *quality])
        expected_requested = set(_split_defects(defect_type))
        if not expected_requested and defect_type:
            expected_requested = {str(defect_type).lower()}

        # Shared observations make every diagnosis auditable without repeating
        # SQL queries or creating duplicate evidence rows in a run.
        event_scrap = sum(1 for row in event_cycles if _scrap(row))
        base_scrap = sum(1 for row in baseline_cycles if _scrap(row))
        event_rate = event_scrap / len(event_cycles) if event_cycles else None
        base_rate = base_scrap / len(baseline_cycles) if baseline_cycles else None
        scrap_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:scrap_rate",
            metric="scrap_rate",
            start=start,
            end=end,
            observation={"stat": "rate", "value": event_rate, "unit": "fraction", "n": len(event_cycles)},
            baseline={"value": base_rate, "unit": "fraction", "n": len(baseline_cycles)} if base_rate is not None else None,
            delta=event_rate - base_rate if event_rate is not None and base_rate is not None else None,
            supports=event_rate is not None and (base_rate is None or event_rate > base_rate),
        )

        quality_ev = self._evidence(
            evidence,
            source_kind="quality_check",
            source_ref=f"{machine_id}:{production_order_id}:quality",
            metric="defect_count",
            start=start,
            end=end,
            observation={
                "stat": "count",
                "value": sum(defect_counts.values()),
                "unit": "defects",
                "n": len(quality),
                "by_type": dict(defect_counts),
            },
            supports=bool(defect_counts),
        )

        related_note_evidence: list[Evidence] = []
        for row in notes[:10]:
            note_ref = str(row.get("note_id") or f"note:{_timestamp(row)}")
            related_note_evidence.append(
                self._evidence(
                    evidence,
                    source_kind="operator_note",
                    source_ref=note_ref,
                    metric="operator_note",
                    start=start,
                    end=end,
                    observation={"stat": "text", "n": 1},
                    supports=True,
                    excerpt=str(row.get("note_text") or ""),
                )
            )

        maintenance_evidence: list[Evidence] = []
        for row in maintenance[:10]:
            event_ref = str(row.get("event_id") or f"maintenance:{_timestamp(row)}")
            maintenance_evidence.append(
                self._evidence(
                    evidence,
                    source_kind="maintenance_event",
                    source_ref=event_ref,
                    metric="maintenance_event",
                    start=start,
                    end=end,
                    observation={
                        "event_type": row.get("event_type"),
                        "duration_min": _num(row, "duration_min"),
                        "severity": row.get("severity"),
                    },
                    supports=True,
                    excerpt=str(row.get("description") or ""),
                )
            )

        candidates: list[tuple[float, Hypothesis]] = []

        def add_candidate(
            *,
            code: str,
            label: str,
            score: float,
            supporting: list[Evidence],
            contradicting: list[Evidence] = (),
            candidate_missing: list[str] | None = None,
            next_check: str,
        ) -> None:
            # When the incident carries a defect classification, keep the
            # ranking causally relevant to that signal.  A maintenance event
            # is allowed to surface the restart hypothesis even when the
            # quality check has no single defect label (S005).
            candidate_hints = {
                "low_barrel_temperature_zone_2": {"short_shot"},
                "high_injection_pressure_low_clamp_force": {"flash"},
                "unstable_cooling_mold_temperature": {"warpage"},
                "material_change_incomplete_purge": {"bubbles"},
                "restart_thermal_instability": {"multiple", "short_shot", "flash", "sink_mark"},
                "progressive_mold_wear_dimension_drift": {"dimension_out_of_tolerance"},
            }
            if expected_requested and not (expected_requested & candidate_hints.get(code, set())):
                return
            if code == "restart_thermal_instability" and "multiple" not in expected_requested and not restart_events:
                return
            if code not in {"restart_thermal_instability", "progressive_mold_wear_dimension_drift"}:
                observed_hints = candidate_hints.get(code, set()) & set(defect_counts)
                if not observed_hints:
                    return
            supporting_ids = [item.id for item in supporting if item.supports]
            contradicting_ids = [item.id for item in contradicting if not item.supports]
            local_missing = list(dict.fromkeys([*missing, *(candidate_missing or [])]))
            confidence = self._candidate_confidence(score, len(supporting_ids), local_missing)
            candidates.append(
                (
                    score,
                    Hypothesis(
                        code,
                        label,
                        confidence,
                        supporting_ids,
                        contradicting_ids,
                        local_missing,
                        next_check,
                    ),
                )
            )

        # S001 — low zone 2 temperature / short shots.
        temps = _values(event_cycles, "barrel_temp_zone2_c")
        baseline_temps = _values(baseline_cycles, "barrel_temp_zone2_c")
        event_temp, base_temp = _safe_median(temps), _safe_median(baseline_temps)
        temp_delta = event_temp - base_temp if event_temp is not None and base_temp is not None else None
        s001_support: list[Evidence] = []
        if event_temp is not None:
            s001_temp = self._evidence(
                evidence,
                source_kind="cycle_aggregate",
                source_ref=f"{machine_id}:{production_order_id}:zone2",
                metric="barrel_temp_zone2_c",
                start=start,
                end=end,
                observation={"stat": "median", "value": event_temp, "unit": "C", "n": len(temps)},
                baseline={"value": base_temp, "unit": "C", "n": len(baseline_temps)} if base_temp is not None else None,
                delta=temp_delta,
                supports=event_temp < 205 and (temp_delta is None or temp_delta <= -3),
            )
            s001_support.append(s001_temp)
        injection = _values(event_cycles, "injection_time_s")
        baseline_injection = _values(baseline_cycles, "injection_time_s")
        if injection:
            inj = _safe_mean(injection)
            binj = _safe_mean(baseline_injection)
            s001_support.append(
                self._evidence(
                    evidence,
                    source_kind="cycle_aggregate",
                    source_ref=f"{machine_id}:{production_order_id}:injection_time",
                    metric="injection_time_s",
                    start=start,
                    end=end,
                    observation={"stat": "mean", "value": inj, "unit": "s", "n": len(injection)},
                    baseline={"value": binj, "unit": "s", "n": len(baseline_injection)} if binj is not None else None,
                    delta=inj - binj if binj is not None else None,
                    supports=binj is not None and abs(inj - binj) >= 0.1,
                )
            )
        s001_score = (3.0 if event_temp is not None and event_temp < 205 else 0.0)
        s001_score += 1.5 if temp_delta is not None and temp_delta <= -3 else 0.0
        s001_score += 1.8 if self._supports_defect(defect_counts, {"short_shot"}) else 0.0
        s001_score += 1.0 if any("short shot" in (item.excerpt or "").lower() or "zone 2" in (item.excerpt or "").lower() for item in related_note_evidence) else 0.0
        s001_score += 0.8 if "short_shot" in expected_requested else 0.0
        add_candidate(
            code="low_barrel_temperature_zone_2",
            label="Température zone 2 trop basse",
            score=s001_score,
            supporting=[*s001_support, scrap_ev, quality_ev, *related_note_evidence],
            candidate_missing=["barrel_temp_zone2_c"] if event_temp is None else [],
            next_check="inspect_barrel_zone_2_heating",
        )

        # S002 — high pressure combined with reduced clamp force / flash.
        pressure = _values(event_cycles, "peak_pressure_bar")
        baseline_pressure = _values(baseline_cycles, "peak_pressure_bar")
        clamp = _values(event_cycles, "clamp_force_kn")
        baseline_clamp = _values(baseline_cycles, "clamp_force_kn")
        p_med, bp_med = _safe_median(pressure), _safe_median(baseline_pressure)
        c_med, bc_med = _safe_median(clamp), _safe_median(baseline_clamp)
        pressure_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:pressure_clamp",
            metric="peak_pressure_bar",
            start=start,
            end=end,
            observation={"stat": "median", "value": p_med, "unit": "bar", "n": len(pressure)},
            baseline={"value": bp_med, "unit": "bar", "n": len(baseline_pressure)} if bp_med is not None else None,
            delta=p_med - bp_med if p_med is not None and bp_med is not None else None,
            supports=p_med is not None and (p_med > 900 or (bp_med is not None and p_med > bp_med * 1.05)),
        )
        clamp_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:clamp_force",
            metric="clamp_force_kn",
            start=start,
            end=end,
            observation={"stat": "median", "value": c_med, "unit": "kN", "n": len(clamp)},
            baseline={"value": bc_med, "unit": "kN", "n": len(baseline_clamp)} if bc_med is not None else None,
            delta=c_med - bc_med if c_med is not None and bc_med is not None else None,
            supports=c_med is not None and bc_med is not None and c_med < bc_med * 0.97,
        )
        s002_score = (2.8 if pressure_ev.supports else 0.0) + (2.2 if clamp_ev.supports else 0.0)
        s002_score += 2.0 if self._supports_defect(defect_counts, {"flash"}) else 0.0
        s002_score += 0.8 if "flash" in expected_requested else 0.0
        add_candidate(
            code="high_injection_pressure_low_clamp_force",
            label="Pression d'injection élevée et effort de verrouillage insuffisant",
            score=s002_score,
            supporting=[pressure_ev, clamp_ev, scrap_ev, quality_ev],
            candidate_missing=[key for key, values in (("peak_pressure_bar", pressure), ("clamp_force_kn", clamp)) if not values],
            next_check="compare_peak_pressure_and_clamp_force_to_order_nominal",
        )

        # S003 — unstable cooling / mould temperature / warpage.
        cooling = _values(event_cycles, "cooling_time_s")
        baseline_cooling = _values(baseline_cycles, "cooling_time_s")
        mold_temp = _values(event_cycles, "mold_temperature_c")
        baseline_mold_temp = _values(baseline_cycles, "mold_temperature_c")
        energy = _values(event_cycles, "energy_kwh")
        baseline_energy = _values(baseline_cycles, "energy_kwh")
        cool_sd, base_cool_sd = _safe_stdev(cooling), _safe_stdev(baseline_cooling)
        mold_sd, base_mold_sd = _safe_stdev(mold_temp), _safe_stdev(baseline_mold_temp)
        cool_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:cooling",
            metric="cooling_time_s",
            start=start,
            end=end,
            observation={"stat": "stdev", "value": cool_sd, "unit": "s", "n": len(cooling)},
            baseline={"value": base_cool_sd, "unit": "s", "n": len(baseline_cooling)} if base_cool_sd is not None else None,
            delta=cool_sd - base_cool_sd if cool_sd is not None and base_cool_sd is not None else None,
            supports=cool_sd is not None and (base_cool_sd is None or cool_sd > max(2.5, base_cool_sd * 1.5)),
        )
        mold_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:mold_temperature",
            metric="mold_temperature_c",
            start=start,
            end=end,
            observation={"stat": "stdev", "value": mold_sd, "unit": "C", "n": len(mold_temp)},
            baseline={"value": base_mold_sd, "unit": "C", "n": len(baseline_mold_temp)} if base_mold_sd is not None else None,
            delta=mold_sd - base_mold_sd if mold_sd is not None and base_mold_sd is not None else None,
            supports=mold_sd is not None and (base_mold_sd is None or mold_sd > max(3.0, base_mold_sd * 1.35)),
        )
        energy_mean, base_energy_mean = _safe_mean(energy), _safe_mean(baseline_energy)
        energy_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:energy",
            metric="energy_kwh",
            start=start,
            end=end,
            observation={"stat": "mean", "value": energy_mean, "unit": "kWh", "n": len(energy)},
            baseline={"value": base_energy_mean, "unit": "kWh", "n": len(baseline_energy)} if base_energy_mean is not None else None,
            delta=energy_mean - base_energy_mean if energy_mean is not None and base_energy_mean is not None else None,
            supports=energy_mean is not None and base_energy_mean is not None and energy_mean > base_energy_mean * 1.05,
        )
        s003_score = (2.4 if cool_ev.supports else 0.0) + (1.8 if mold_ev.supports else 0.0)
        s003_score += 1.0 if energy_ev.supports else 0.0
        s003_score += 2.0 if self._supports_defect(defect_counts, {"warpage"}) else 0.0
        s003_score += 0.8 if "warpage" in expected_requested else 0.0
        add_candidate(
            code="unstable_cooling_mold_temperature",
            label="Refroidissement et température du moule instables",
            score=s003_score,
            supporting=[cool_ev, mold_ev, energy_ev, scrap_ev, quality_ev],
            candidate_missing=[key for key, values in (("cooling_time_s", cooling), ("mold_temperature_c", mold_temp)) if not values],
            next_check="trend_cooling_time_and_mold_temperature_by_cycle",
        )

        # S004 — material change / purge or drying issue / bubbles.
        change_events = [
            item
            for item in maintenance_evidence
            if any(token in (item.excerpt or "").lower() for token in ("changement mat", "material change", "purge"))
        ]
        material_note = [
            item
            for item in related_note_evidence
            if any(token in (item.excerpt or "").lower() for token in ("bulle", "sechage", "matiere", "granule"))
        ]
        s004_score = (3.0 if change_events else 0.0) + (1.6 if material_note else 0.0)
        s004_score += 2.0 if self._supports_defect(defect_counts, {"bubbles"}) else 0.0
        s004_score += 0.8 if "bubbles" in expected_requested else 0.0
        add_candidate(
            code="material_change_incomplete_purge",
            label="Changement de matière avec purge ou séchage insuffisant",
            score=s004_score,
            supporting=[*change_events, *material_note, scrap_ev, quality_ev],
            next_check="verify_material_drying_and_purge_after_lot_change",
        )

        # S005 — restart after stop / temporary thermal instability.
        restart_events = [
            item
            for item in maintenance_evidence
            if any(token in (item.excerpt or "").lower() for token in ("redemarrage", "arrêt machine", "arret machine", "restart"))
        ]
        first_half = event_cycles[: max(1, len(event_cycles) // 2)]
        second_half = event_cycles[len(event_cycles) // 2 :]
        first_scrap = sum(1 for row in first_half if _scrap(row)) / len(first_half) if first_half else None
        second_scrap = sum(1 for row in second_half if _scrap(row)) / len(second_half) if second_half else None
        early_rate_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:restart_transition",
            metric="early_scrap_rate",
            start=start,
            end=end,
            observation={"stat": "first_half_rate", "value": first_scrap, "unit": "fraction", "n": len(first_half)},
            baseline={"value": second_scrap, "unit": "fraction", "n": len(second_half)} if second_scrap is not None else None,
            delta=first_scrap - second_scrap if first_scrap is not None and second_scrap is not None else None,
            supports=first_scrap is not None and second_scrap is not None and first_scrap > second_scrap + 0.05,
        )
        z1 = _values(event_cycles, "barrel_temp_zone1_c")
        z2 = _values(event_cycles, "barrel_temp_zone2_c")
        z1_sd, z2_sd = _safe_stdev(z1), _safe_stdev(z2)
        thermal_ev = self._evidence(
            evidence,
            source_kind="cycle_aggregate",
            source_ref=f"{machine_id}:{production_order_id}:thermal_stability",
            metric="barrel_temperature_stability",
            start=start,
            end=end,
            observation={"zone1_stdev": z1_sd, "zone2_stdev": z2_sd, "n": min(len(z1), len(z2))},
            supports=(z1_sd is not None and z1_sd >= 3) or (z2_sd is not None and z2_sd >= 3),
        )
        observed_defects = set(defect_counts)
        s005_score = (3.2 if restart_events else 0.0) + (1.5 if early_rate_ev.supports else 0.0)
        s005_score += 1.2 if thermal_ev.supports else 0.0
        s005_score += 1.8 if len(observed_defects.intersection({"short_shot", "flash", "sink_mark"})) >= 2 else 0.0
        s005_score += 0.8 if expected_requested.intersection({"short_shot", "flash", "sink_mark"}) else 0.0
        add_candidate(
            code="restart_thermal_instability",
            label="Redémarrage après arrêt et instabilité thermique transitoire",
            score=s005_score,
            supporting=[*restart_events, early_rate_ev, thermal_ev, scrap_ev, quality_ev, *related_note_evidence],
            next_check="verify_restart_sequence_and_wait_for_thermal_steady_state",
        )

        # S006 — progressive dimensional drift / mold wear.
        dim_slope, dim_delta, dim_n = _trend(quality, "dimension_deviation_mm")
        weight_slope, weight_delta, weight_n = _trend(quality, "measured_weight_g")
        dimension_ev = self._evidence(
            evidence,
            source_kind="quality_check",
            source_ref=f"{machine_id}:{production_order_id}:dimension_trend",
            metric="dimension_deviation_mm",
            start=start,
            end=end,
            observation={"stat": "trend", "slope_per_day": dim_slope, "first_last_delta": dim_delta, "n": dim_n, "unit": "mm"},
            supports=dim_slope is not None and dim_slope > 0.02 and dim_delta is not None and dim_delta > 0.05,
        )
        weight_ev = self._evidence(
            evidence,
            source_kind="quality_check",
            source_ref=f"{machine_id}:{production_order_id}:weight_trend",
            metric="measured_weight_g",
            start=start,
            end=end,
            observation={"stat": "trend", "slope_per_day": weight_slope, "first_last_delta": weight_delta, "n": weight_n, "unit": "g"},
            supports=weight_delta is not None and abs(weight_delta) > 0.2,
        )
        wear_notes = [
            item
            for item in related_note_evidence
            if any(token in (item.excerpt or "").lower() for token in ("usure", "cotes", "derive dimensionnelle", "moule"))
        ]
        s006_score = (3.8 if dimension_ev.supports else 0.0) + (0.8 if weight_ev.supports else 0.0)
        s006_score += 1.6 if wear_notes else 0.0
        s006_score += 1.2 if "dimension_out_of_tolerance" in expected_requested else 0.0
        add_candidate(
            code="progressive_mold_wear_dimension_drift",
            label="Usure progressive du moule et dérive dimensionnelle",
            score=s006_score,
            supporting=[dimension_ev, weight_ev, *wear_notes, quality_ev],
            candidate_missing=["dimension_deviation_mm"] if dim_n < 3 else [],
            next_check="inspect_mold_cavity_dimensions_and_tool_wear",
        )

        # Do not surface arbitrary low-score explanations.  A top-2 result is
        # useful only when a candidate has at least two points of measurable
        # support; this keeps healthy windows from becoming incidents merely
        # because a naturally noisy sensor exists.
        ranked = sorted(
            ((score, hypothesis) for score, hypothesis in candidates if score >= 2.0),
            key=lambda item: (-item[0], item[1].cause_code),
        )[:2]
        if not ranked:
            raise InsufficientDataError("No diagnostic hypothesis reached the evidence threshold")

        confidence = max(hypothesis.confidence for _, hypothesis in ranked)
        data_quality = "sufficient"
        if "baseline_cycles" in missing:
            data_quality = "insufficient_baseline"
        elif missing:
            data_quality = "insufficient_samples"
        symptom_by_defect = {
            "short_shot": "short_shot_increase",
            "flash": "flash_increase",
            "bubbles": "bubbles_increase",
            "warpage": "warpage_increase",
            "dimension_out_of_tolerance": "dimension_drift",
            "multiple": "quality_anomaly",
        }
        incident = {
            "id": incident_id or str(uuid5(NAMESPACE_URL, f"iddrv:incident:{machine_id}:{production_order_id}:{start.isoformat()}")),
            "machine_id": machine_id,
            "machine_erp_ref": machine_erp_ref,
            "production_order_id": production_order_id,
            "status": "open",
            "severity": "high" if event_rate is not None and event_rate >= 0.2 else "medium",
            "symptom": symptom_by_defect.get(str(defect_type).lower(), "quality_anomaly"),
            "defect_type": defect_type,
            "started_at": start.isoformat(),
            "ended_at": end.isoformat(),
            "data_cutoff": end.isoformat(),
            "confidence": "high" if confidence >= 0.75 else "medium" if confidence >= 0.5 else "low",
        }
        return Investigation(incident, evidence, [hypothesis for _, hypothesis in ranked], data_quality)


class DiagnosticEngine(DeterministicInvestigator):
    """Legacy-compatible engine used by the current API and S001 tests."""

    def __init__(self, repository: DiagnosticRepository, *, baseline_multiplier: float = 1.0):
        # Keep the original permissive behavior for existing API clients while
        # exposing the stricter DeterministicInvestigator for new integrations.
        super().__init__(repository, baseline_multiplier=baseline_multiplier, abstain_on_insufficient=False)


__all__ = ["DiagnosticEngine", "DeterministicInvestigator", "Investigator"]
