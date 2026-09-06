from datetime import datetime, timedelta, timezone
from ingest.context_models import CycleContext, DeclarationCandidate
from ingest.context_matching import choose_context

START = datetime(2026, 9, 5, 5, tzinfo=timezone.utc)

def candidate(id='a', **kwargs):
    return DeclarationCandidate(**(dict(id=id, revision_id=id+'1', site_id=1, machine_id=606,
        order_ref='OF12', start=START, end=START+timedelta(hours=8), bounds_source='source') | kwargs))

def test_overlapping_orders_remain_ambiguous():
    result = choose_context(CycleContext(1,606,START), [candidate(), candidate('b')])
    assert result.status == 'ambiguous'
    assert result.declaration_id is None
    assert set(result.candidate_ids) == {'a', 'b'}

def test_unique_context_and_half_open_boundary():
    assert choose_context(CycleContext(1,606,START), [candidate()]).status == 'matched'
    assert choose_context(CycleContext(1,606,START+timedelta(hours=8)), [candidate()]).status == 'awaiting_erp'

def test_scope_and_estimated_bounds():
    assert choose_context(CycleContext(2,606,START), [candidate()]).status == 'awaiting_erp'
    assert choose_context(CycleContext(1,607,START), [candidate()]).status == 'awaiting_erp'
    assert choose_context(CycleContext(1,606,START), [candidate(bounds_source='calendar')]).status == 'provisional'

def test_reopening_does_not_fill_production_pause():
    periods = [candidate(), candidate('b', start=START+timedelta(days=2), end=START+timedelta(days=2,hours=8))]
    assert choose_context(CycleContext(1,606,START+timedelta(days=1)), periods).status == 'awaiting_erp'
    assert choose_context(CycleContext(1,606,START+timedelta(days=2)), periods).declaration_id == 'b'
