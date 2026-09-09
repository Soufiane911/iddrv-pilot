"""Bounded synthetic software-test input, never a production qualification dataset.

No repository data is read. CSVs are generated from an explicit periodic signal.
"""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd

MACHINES = ('152', '606', '1003')
CYCLES_PER_MACHINE = 1200


def generate(output: Path) -> Path:
    from ml.process_drift import RAW_NUMERIC_FEATURES

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for machine_index, machine in enumerate(MACHINES):
        i = np.arange(CYCLES_PER_MACHINE)
        phase = i % 200
        # Volatility starts before scrap: exercise future-only event construction.
        amplitude = np.where((phase >= 100) & (phase < 145), 8.0, 0.05)
        frame = pd.DataFrame({
            name: 10 * (j + 1) + machine_index + amplitude * np.sin(i * (0.7 + j / 20))
            for j, name in enumerate(RAW_NUMERIC_FEATURES)
        })
        frame['timestamp'] = pd.date_range('2024-01-01', periods=len(i), freq='min', tz='UTC') + pd.Timedelta(seconds=machine_index)
        frame['machine_erp_ref'] = machine
        frame['scrap_flag'] = ((phase >= 120) & (phase < 145)).astype(int)
        frame.to_csv(output / f'machine_cycles_{machine}.csv', index=False)
    (output / 'provenance.json').write_text(json.dumps({
        'synthetic': True, 'purpose': 'software-contract-tests-only',
        'production_qualified': False, 'cycles_per_machine': CYCLES_PER_MACHINE,
        'machines': list(MACHINES), 'generator': 'periodic-signal-v1',
    }, sort_keys=True))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    generate(args.output)
