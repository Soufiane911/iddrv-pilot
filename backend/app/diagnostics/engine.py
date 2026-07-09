"""S001 deterministic investigation engine."""

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from uuid import NAMESPACE_URL, uuid5

from .models import Evidence, Hypothesis, InsufficientDataError, Investigation
from .repository import DiagnosticRepository


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _num(row: Mapping, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None:
            try: return float(value)
            except (TypeError, ValueError): pass
    return None


class DiagnosticEngine:
    def __init__(self, repository: DiagnosticRepository, *, baseline_multiplier: float = 1.0):
        self.repository = repository
        self.baseline_multiplier = baseline_multiplier

    @staticmethod
    def _evidence_id(source_ref, metric):
        return str(uuid5(NAMESPACE_URL, f"iddrv:evidence:{source_ref}:{metric}"))

    def investigate(self, *, machine_id, machine_erp_ref=None, production_order_id, started_at, ended_at, defect_type="short_shot", incident_id=None):
        start, end = _dt(started_at), _dt(ended_at)
        duration = max(end - start, timedelta(minutes=1))
        baseline_start, baseline_end = start - duration, start
        event_cycles = list(self.repository.cycles(machine_id, start, end))
        baseline_cycles = list(self.repository.cycles(machine_id, baseline_start, baseline_end))
        quality = list(self.repository.quality_checks(machine_id, start, end))
        notes = list(self.repository.operator_notes(machine_id, start - timedelta(hours=2), end + timedelta(hours=2)))
        if not event_cycles and not quality:
            raise InsufficientDataError("No cycle or quality data exists in the incident window")
        evidence: list[Evidence] = []
        event_scrap = sum(1 for r in event_cycles if bool(r.get("scrap_flag")) or str(r.get("part_quality_status", "")).lower() == "scrap")
        base_scrap = sum(1 for r in baseline_cycles if bool(r.get("scrap_flag")) or str(r.get("part_quality_status", "")).lower() == "scrap")
        event_rate = event_scrap / len(event_cycles) if event_cycles else None
        base_rate = base_scrap / len(baseline_cycles) if baseline_cycles else None
        ids = []
        if event_rate is not None and base_rate is not None:
            ref = f"{machine_id}:{production_order_id}:scrap_rate"
            ev = Evidence(self._evidence_id(ref, "scrap_rate"), "cycle_aggregate", ref, "scrap_rate", {"start": start.isoformat(), "end": end.isoformat()}, {"stat": "rate", "value": event_rate, "unit": "fraction", "n": len(event_cycles)}, {"value": base_rate, "unit": "fraction", "n": len(baseline_cycles)}, event_rate - base_rate, event_rate > base_rate)
            evidence.append(ev); ids.append(ev.id)
        temps = [_num(r, "barrel_temp_zone2_c") for r in event_cycles]; temps = [v for v in temps if v is not None]
        btemps = [_num(r, "barrel_temp_zone2_c") for r in baseline_cycles]; btemps = [v for v in btemps if v is not None]
        if temps:
            ref = f"{machine_id}:{production_order_id}:zone2"
            ev = Evidence(self._evidence_id(ref, "barrel_temp_zone2_c"), "cycle_aggregate", ref, "barrel_temp_zone2_c", {"start": start.isoformat(), "end": end.isoformat()}, {"stat": "median", "value": median(temps), "unit": "C", "n": len(temps)}, {"value": median(btemps), "unit": "C", "n": len(btemps)} if btemps else None, median(temps) - median(btemps) if btemps else None, bool(btemps and median(temps) < median(btemps)), None)
            evidence.append(ev)
            if ev.supports: ids.append(ev.id)
        defects = [str(r.get("defect_type") or "").strip() for r in quality if r.get("defect_type")]
        if not defects:
            defects = [str(r.get("defect_type") or "").strip() for r in event_cycles if r.get("defect_type")]
        if defects:
            ref = f"{machine_id}:{production_order_id}:quality"
            ev = Evidence(self._evidence_id(ref, "defect_count"), "quality_check", ref, "defect_count", {"start": start.isoformat(), "end": end.isoformat()}, {"stat": "count", "value": len(defects), "unit": "defects", "n": len(quality) or len(event_cycles)}, None, None, defect_type in defects, "; ".join(sorted(set(defects))))
            evidence.append(ev)
            if ev.supports: ids.append(ev.id)
        related = [n for n in notes if str(n.get("production_order_id", "")) in ("", str(production_order_id))]
        if related:
            n = related[0]; ref = str(n.get("note_id", "operator-note"))
            ev = Evidence(self._evidence_id(ref, "operator_note"), "operator_note", ref, "operator_note", {"start": start.isoformat(), "end": end.isoformat()}, {"stat": "text", "value": 1, "unit": "note", "n": len(related)}, excerpt=str(n.get("note_text", "")))
            evidence.append(ev); ids.append(ev.id)
        support = sum(1 for e in evidence if e.supports)
        missing = [] if btemps and baseline_cycles else ["baseline_cycles"]
        confidence = min(0.98, 0.5 + 0.1 * support + (0.15 if temps and btemps else 0))
        hypothesis = Hypothesis("low_barrel_temperature_zone_2", "Température zone 2 trop basse", confidence, ids, [], missing, "inspect_barrel_zone_2_heating")
        incident = {"id": incident_id or str(uuid5(NAMESPACE_URL, f"iddrv:incident:{machine_id}:{production_order_id}:{start.isoformat()}")), "machine_id": machine_id, "machine_erp_ref": machine_erp_ref, "production_order_id": production_order_id, "status": "open", "severity": "high" if event_rate and base_rate and event_rate > base_rate * 2 else "medium", "symptom": "short_shot_increase", "defect_type": defect_type, "started_at": start.isoformat(), "ended_at": end.isoformat(), "data_cutoff": end.isoformat(), "confidence": "high" if confidence >= .75 else "medium"}
        return Investigation(incident, evidence, [hypothesis], "sufficient" if not missing else "insufficient_baseline")
