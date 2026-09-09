"""CI uses a tiny SYNTHETIC forest, NOT evidence of approved-forest equivalence.
Real-package exact scores are a separate explicitly optional test below.
"""
import copy
import json
import os
from pathlib import Path

import numpy as np
import pytest
from sklearn.ensemble import IsolationForest

from ml.summary6 import ContractError, score_cycles, load_package
from ml.summary6.registry import write_package, digest

GOLDEN = json.loads((Path(__file__).parent / 'test_summary6_fixtures/golden.json').read_text())


@pytest.fixture
def tiny(tmp_path):
    model = IsolationForest(n_estimators=3, max_samples=16, random_state=42).fit(
        np.random.default_rng(42).normal(size=(32, 6)))
    path = tmp_path / 'tiny'
    pin = write_package(path, models={('M1', 'R1'): model},
                        contexts=[GOLDEN['context']], source_sha256='tiny-synthetic',
                        scientific_status='TINY_SYNTHETIC_TEST_ONLY', provenance={})
    return load_package(path, expected_manifest_sha256=pin, allow_test_package=True), path, pin


def test_frozen_features_and_boundaries(tiny):
    p, _, _ = tiny
    results = score_cycles(GOLDEN['cycles'], package=p)
    by = {r['cycle_counter']: r for r in results}
    assert by[59]['instant_score'] is None
    assert by[60]['instant_score'] is None
    assert by[79]['instant_score'] is not None and by[79]['decision_score'] is None
    assert by[81]['decision_score'] is not None and by[83]['alert'] is None
    assert by[84]['status'] == 'available'
    np.testing.assert_array_equal([r['features'] for r in results if r['features'] is not None], GOLDEN['features'])
    for n in range(84, 91):
        assert by[n]['decision_score'] == min(by[k]['instant_score'] for k in range(n-2, n+1))
        assert by[n]['alert'] == (by[n]['decision_score'] >= by[n]['threshold'])


def test_causal_prefix_reset_reload(tiny):
    p, path, pin = tiny
    cycles = copy.deepcopy(GOLDEN['cycles'])
    before = score_cycles(cycles[:65], package=p)
    cycles[65]['sensors']['cycle_time_s'] = None
    assert score_cycles(cycles, package=p)[:65] == before
    assert score_cycles(cycles, package=p)[65]['reason'] == 'incomplete_sensors'
    assert score_cycles(GOLDEN['cycles'], package=load_package(path, expected_manifest_sha256=pin, allow_test_package=True)) == score_cycles(GOLDEN['cycles'], package=p)
    new_lot = copy.deepcopy(GOLDEN['cycles'][:40])
    for r in new_lot:
        r['lot_id'] = 'new-lot'
    assert score_cycles(new_lot, package=p)[-1]['instant_score'] is None


@pytest.mark.parametrize('fault', ['duplicate', 'gap', 'recipe', 'lot', 'source', 'units', 'counter'])
def test_contract_rejects(tiny, fault):
    cycles = copy.deepcopy(GOLDEN['cycles'])
    if fault == 'duplicate': cycles[1]['cycle_counter'] = 20
    if fault == 'gap': cycles[1]['cycle_counter'] = 22
    if fault == 'recipe': cycles[1]['recipe_id'] = 'R2'
    if fault == 'lot': cycles[1]['lot_id'] = 'different'
    if fault == 'source': cycles[1]['source_id'] = 'different'
    if fault == 'units': cycles[1]['units']['peak_pressure_bar'] = 'Pa'
    if fault == 'counter': cycles[1]['cycle_counter'] = True
    with pytest.raises(ContractError): score_cycles(cycles, package=tiny[0])


def test_abstentions(tiny):
    p = tiny[0]
    assert score_cycles(GOLDEN['cycles'][-20:], package=p)[-1]['reason'] == 'incomplete_prefix'
    cycles = copy.deepcopy(GOLDEN['cycles'])
    for r in cycles: r['recipe_id'] = 'unknown'
    assert score_cycles(cycles, package=p)[-1]['reason'] == 'unknown_context'
    cycles = copy.deepcopy(GOLDEN['cycles'])
    for r in cycles[:40]: r['sensors']['cycle_time_s'] += 10000
    assert score_cycles(cycles, package=p)[39]['reason'] == 'anchor_out_of_guard'
    cycles = copy.deepcopy(GOLDEN['cycles'])
    del cycles[10]['sensors']['cycle_time_s']
    assert score_cycles(cycles, package=p)[-1]['reason'] == 'incomplete_sensors'


def test_tampering_before_deserialization(tiny, monkeypatch):
    _, path, pin = tiny
    import ml.summary6.registry as registry
    def forbidden(*args, **kwargs):
        raise AssertionError('must not deserialize tampered package')
    monkeypatch.setattr(registry.joblib, 'load', forbidden)
    payload = path / 'models.joblib'
    payload.write_bytes(payload.read_bytes() + b'tampered')
    with pytest.raises(ValueError, match='models SHA256'): load_package(path, expected_manifest_sha256=pin, allow_test_package=True)
    with pytest.raises(ValueError, match='manifest SHA256'): load_package(path, expected_manifest_sha256='0'*64)


def test_guard_and_threshold_equality(tiny):
    from dataclasses import replace
    p = tiny[0]
    contexts = copy.deepcopy(p.contexts)
    contexts[('M1', 'R1')].update(center=[0.]*8, scale=[1.]*8)
    p = replace(p, contexts=contexts)
    cycles = copy.deepcopy(GOLDEN['cycles'])
    for row in cycles:
        row['sensors'] = {s: 3. for s in row['sensors']}
    result = score_cycles(cycles, package=p)[-1]
    assert result['status'] == 'available'  # guard is >3, not >=3
    contexts[('M1', 'R1')]['threshold'] = result['decision_score']
    assert score_cycles(cycles, package=p)[-1]['alert'] is True
    for row in cycles[:40]:
        row['sensors']['cycle_time_s'] = np.nextafter(3., np.inf)
    assert score_cycles(cycles, package=p)[-1]['reason'] == 'anchor_out_of_guard'


def test_all_mature_prefixes(tiny):
    p = tiny[0]
    full = score_cycles(GOLDEN['cycles'], package=p)
    for length in range(59, len(full) + 1):
        assert score_cycles(GOLDEN['cycles'][:length], package=p) == full[:length]


def test_approved_package_exact_golden():
    path, pin = os.getenv('SUMMARY6_TEST_PACKAGE'), os.getenv('SUMMARY6_TEST_MANIFEST_SHA256')
    if not path or not pin:
        pytest.skip('approved PRIVATE package absent: tiny tests do NOT certify real model scores')
    p = load_package(path, expected_manifest_sha256=pin)
    assert len(p.models) == 6
    results = score_cycles(GOLDEN['cycles'], package=p)
    scored = [r for r in results if r['instant_score'] is not None]
    np.testing.assert_array_equal([r['features'] for r in scored], GOLDEN['features'])
    np.testing.assert_array_equal([r['instant_score'] for r in scored], GOLDEN['instant_scores'])
    np.testing.assert_array_equal([r['decision_score'] for r in scored[2:]], GOLDEN['decision_scores'])
    assert all(r['threshold'] == GOLDEN['threshold'] for r in results)


def test_approved_export_all_six_models_exact():
    """Optional local source-vs-compact serialization check; no retraining."""
    from io import BytesIO
    import warnings
    import joblib
    from ml.summary6.registry import SOURCE_SHA256
    path, pin = os.getenv('SUMMARY6_TEST_PACKAGE'), os.getenv('SUMMARY6_TEST_MANIFEST_SHA256')
    source = Path('/Users/soufianehamzaoui/Desktop/EPSI/ProjetSeptembre/output/hdt-feature-hypotheses-2026-09-07/run01/confirmation/candidate_61007.joblib')
    if not path or not pin or not source.is_file():
        pytest.skip('private approved source/package absent: six-model equivalence not certified in CI')
    raw = source.read_bytes()
    assert digest(raw) == SOURCE_SHA256  # BEFORE deserialize
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        original = joblib.load(BytesIO(raw))
    packaged = load_package(path, expected_manifest_sha256=pin)
    probes = np.concatenate([np.asarray(GOLDEN['features']),
                             np.random.default_rng(61007).uniform(0, 5, size=(128, 6))])
    assert set(packaged.models) == set(original['models'])
    for key in original['models']:
        np.testing.assert_array_equal(packaged.models[key].score_samples(probes),
                                      original['models'][key].score_samples(probes))
        np.testing.assert_array_equal(packaged.contexts[key]['center'], original['reference'][key][0])
        np.testing.assert_array_equal(packaged.contexts[key]['scale'], original['reference'][key][1])
        assert packaged.contexts[key]['threshold'] == original['thresholds'][key]
