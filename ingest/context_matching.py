"""Pure candidate selection, never administrative OF lifetime matching."""
from .context_models import CycleContext, DeclarationCandidate, MatchDecision

def choose_context(cycle: CycleContext, candidates: list[DeclarationCandidate]) -> MatchDecision:
    available = {c.id: c for c in candidates if c.site_id == cycle.site_id and c.machine_id == cycle.machine_id
                 and c.start is not None and c.end is not None and c.start <= cycle.ended_at < c.end}
    ids = sorted(available)
    if not ids:
        return MatchDecision('awaiting_erp', None, None, [], None)
    if len(ids) > 1:
        return MatchDecision('ambiguous', None, None, ids, None)
    candidate = available[ids[0]]
    estimated = candidate.bounds_source == 'calendar'
    return MatchDecision('provisional' if estimated else 'matched', candidate.id, candidate.revision_id, ids, .5 if estimated else 1.)
