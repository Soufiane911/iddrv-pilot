"""Minimal port of frozen evaluate.make_features / hdt_methods.features and
feature_study.representations/decisions. See certification provenance.

Batch replay is deliberately stateless: supply the complete lot prefix from
counter 20 (or earlier), never a renumbered trailing window.
"""
import warnings

import numpy as np
import pandas as pd

SENSORS = ('cycle_time_s', 'injection_time_s', 'cooling_time_s',
           'peak_pressure_bar', 'clamp_force_kn', 'mold_temperature_c',
           'barrel_temp_zone2_c', 'energy_kwh')
UNITS = dict(zip(SENSORS, ('s', 's', 's', 'bar', 'kN', 'degC', 'degC', 'kWh')))
FEATURES = ('amplitude_max', 'amplitude_rms', 'amplitude_q75',
            'std_max', 'std_rms', 'std_q75')
POLICY = dict(anchor_start=20, anchor_end=59, guard_mad=3,
              window=20, ddof=0, persistence=3, publication_start=84,
              budget=0.0025, comparison='>=')


class ContractError(ValueError):
    """Malformed chronology/identity/units; never silently repaired."""


def score_cycles(cycles, *, package):
    """Return one result per supplied cycle, in original order.

    Each cycle has source_id, machine_erp_ref, recipe_id, lot_id,
    cycle_counter (integer >=0), units (exact UNITS), and sensors (exact keys).
    Only one lot/context/source per call. A new call resets all state.
    Missing/nonfinite sensor values abstain the whole prefix; do not impute.
    """
    if not isinstance(cycles, list) or not cycles:
        raise ContractError('nonempty list required')
    identity = None
    counters, values = [], []
    missing = False
    for row in cycles:
        if not isinstance(row, dict):
            raise ContractError('cycle must be an object')
        if set(row) != {'source_id', 'machine_erp_ref', 'recipe_id', 'lot_id',
                        'cycle_counter', 'units', 'sensors'}:
            raise ContractError('cycle fields must exactly match contract; no labels/future inputs')
        ids = tuple(row.get(k) for k in ('source_id', 'machine_erp_ref', 'recipe_id', 'lot_id'))
        if not all(isinstance(v, str) and v.strip() for v in ids):
            raise ContractError('source, machine, recipe and lot required')
        if identity is not None and ids != identity:
            raise ContractError('inconsistent lot/source/context: reset with a new call')
        identity = ids
        n = row.get('cycle_counter')
        if type(n) is not int or n < 0:
            raise ContractError('nonnegative integer cycle_counter required')
        if counters and n != counters[-1] + 1:
            raise ContractError('duplicate, gap or unordered cycle_counter')
        counters.append(n)
        if row.get('units') != UNITS:
            raise ContractError('units must exactly match summary6; no conversion')
        sensors = row.get('sensors')
        if not isinstance(sensors, dict) or set(sensors) - set(SENSORS):
            raise ContractError('sensors object contains unsupported keys')
        vector = []
        for sensor in SENSORS:
            v = sensors.get(sensor)
            if v is None or (isinstance(v, (float, int)) and not isinstance(v, bool) and not np.isfinite(v)):
                vector.append(np.nan)
            elif isinstance(v, (float, int)) and not isinstance(v, bool):
                vector.append(float(v))
            else:
                raise ContractError('sensor must be a number or null')
        values.append(vector)
    key = identity[1:3]
    record = package.contexts.get(key)
    results = [dict(runtime_id=package.runtime_id, cycle_counter=n,
                    status='abstained', reason='warmup', features=None,
                    instant_score=None, decision_score=None, threshold=None,
                    alert=None, model_scope='machine_recipe', signals=[])
               for n in counters]
    # Prefix validity is causal: a later missing value cannot erase earlier scores.
    if record is None:
        for r in results:
            r['reason'] = 'unknown_context'
        return results
    center, scale = np.asarray(record['center']), np.asarray(record['scale'])
    frame = pd.DataFrame(values, index=counters, columns=SENSORS)
    anchor = None
    if counters[0] <= 20 and counters[-1] >= 59:
        anchor = frame.loc[20:59].median().to_numpy()
    tail = frame.loc[60:]
    summaries = None
    if anchor is not None:
        z = (tail - anchor) / scale
        mean = z.rolling(20, min_periods=20).mean().abs()
        std = z.rolling(20, min_periods=20).std(ddof=0)
        summary = {}
        for label, data in [('amplitude', mean), ('std', std)]:
            summary[label + '_max'] = data.max(axis=1)
            summary[label + '_rms'] = np.sqrt((data ** 2).mean(axis=1))
            summary[label + '_q75'] = data.quantile(.75, axis=1)
        summaries = pd.DataFrame(summary)
    scores = []
    for i, r in enumerate(results):
        n = counters[i]
        missing = missing or not np.isfinite(values[i]).all()
        r['threshold'] = record['threshold']
        if missing:
            r['reason'] = 'incomplete_sensors'
        elif counters[0] > 20:
            r['reason'] = 'incomplete_prefix'
        elif n < 59:
            pass
        elif np.max(np.abs((anchor - center) / scale)) > 3:
            r['reason'] = 'anchor_out_of_guard'
        elif n < 79:
            pass
        else:
            features = summaries.loc[n].to_numpy()
            with warnings.catch_warnings():
                warnings.simplefilter('error')
                score = float(-package.models[key].score_samples(features.reshape(1, -1))[0])
            if not np.isfinite(features).all() or not np.isfinite(score):
                raise ValueError('summary6 nonfinite feature/score; refusing decision')
            scores.append(score)
            r.update(features=features.tolist(), instant_score=score)
            if len(scores) >= 3:
                r['decision_score'] = min(scores[-3:])
            if n >= 84 and r['decision_score'] is not None:
                r.update(status='available', reason=None,
                         alert=r['decision_score'] >= r['threshold'])
            else:
                r['reason'] = 'publication_warmup'
    return results
