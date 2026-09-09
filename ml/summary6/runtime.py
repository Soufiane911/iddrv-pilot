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
            if v is None:
                vector.append(np.nan)
            elif isinstance(v, (float, int)) and not isinstance(v, bool):
                try:
                    converted = float(v)
                except OverflowError:
                    converted = np.nan
                vector.append(converted if np.isfinite(converted) else np.nan)
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
    guard = None
    numerical_failures = set()
    if counters[0] <= 20 and counters[-1] >= 59:
        try:
            with warnings.catch_warnings(), np.errstate(over='raise', invalid='raise', divide='raise'):
                warnings.simplefilter('error')
                anchor = frame.loc[20:59].median().to_numpy()
                guard = np.abs((anchor - center) / scale)
            if not np.isfinite(anchor).all() or not np.isfinite(guard).all():
                numerical_failures.add(59)
        except (FloatingPointError, RuntimeWarning):
            numerical_failures.add(59)
            anchor = None
    tail = frame.loc[60:]
    summaries = None
    if anchor is not None:
        # Raise, never suppress arithmetic warnings. Record failures at their
        # causal cycle, rather than letting pandas silently reduce seven sensors.
        residuals = []
        for n, row in tail.iterrows():
            try:
                with np.errstate(over='raise', invalid='raise', divide='raise'):
                    residual = (row.to_numpy() - anchor) / scale
                if not np.isfinite(residual).all():
                    numerical_failures.add(n)
            except FloatingPointError:
                numerical_failures.add(n)
                residual = np.full(len(SENSORS), np.nan)
            residuals.append(residual)
        z = pd.DataFrame(residuals, index=tail.index, columns=SENSORS)
        mean = z.rolling(20, min_periods=20).mean().abs()
        std = z.rolling(20, min_periods=20).std(ddof=0)
        summaries = pd.DataFrame(np.nan, index=tail.index, columns=FEATURES)
        for n in tail.index:
            if n < 79:
                continue
            if not (np.isfinite(mean.loc[n]).all() and np.isfinite(std.loc[n]).all()):
                numerical_failures.add(n)
                continue
            summary = {}
            try:
                with warnings.catch_warnings(), np.errstate(over='raise', invalid='raise', divide='raise'):
                    warnings.simplefilter('error')
                    for label, data in [('amplitude', mean.loc[[n]]), ('std', std.loc[[n]])]:
                        summary[label + '_max'] = data.max(axis=1)
                        summary[label + '_rms'] = np.sqrt((data ** 2).mean(axis=1))
                        summary[label + '_q75'] = data.quantile(.75, axis=1)
                features = pd.DataFrame(summary).loc[n].to_numpy()
                if not np.isfinite(features).all():
                    numerical_failures.add(n)
                else:
                    summaries.loc[n] = features
            except (FloatingPointError, RuntimeWarning):
                numerical_failures.add(n)
    numerical_failure = False
    scores = []
    for i, r in enumerate(results):
        n = counters[i]
        missing = missing or not np.isfinite(values[i]).all()
        numerical_failure = numerical_failure or n in numerical_failures
        r['threshold'] = record['threshold']
        if missing:
            r['reason'] = 'incomplete_sensors'
        elif counters[0] > 20:
            r['reason'] = 'incomplete_prefix'
        elif n < 59:
            pass
        elif numerical_failure:
            r['reason'] = 'numerical_failure'
        elif np.max(guard) > 3:
            r['reason'] = 'anchor_out_of_guard'
        elif n < 79:
            pass
        else:
            features = summaries.loc[n].to_numpy()
            try:
                with warnings.catch_warnings(), np.errstate(over='raise', invalid='raise', divide='raise'):
                    warnings.simplefilter('error')
                    score = float(-package.models[key].score_samples(features.reshape(1, -1))[0])
                if not np.isfinite(score):
                    raise FloatingPointError('nonfinite score')
            except (FloatingPointError, RuntimeWarning):
                numerical_failure = True
                r['reason'] = 'numerical_failure'
                continue
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
