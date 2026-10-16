"""Offline regression: strict 30-cycle CSV validation; legacy 5-cycle preserved."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_acquisition import validate_file


def main():
    root = Path(__file__).resolve().parents[1]
    old = root / 'data/raw/D-CAT_B36.csv'
    assert old.is_file()
    original = pd.read_csv(old)
    first_cycle = original.loc[original.run_id == 1].copy()
    assert validate_file(old) == [], '5-cycle regression'
    assert validate_file(old, expected_cycles=30), '5 cycles must not pass 30-cycle gate'
    frames = []
    # Schema / sample timing are faithfully repeated for shape-regression;
    # this is NOT a physical acquisition or performance evidence.
    for i in range(30):
        part = first_cycle.copy()
        part['run_id'] = i + 1
        part['timestamp'] = pd.to_numeric(part['timestamp']) + i * 40000
        frames.append(part)
    with TemporaryDirectory() as tmp:
        dst = Path(tmp) / old.name
        pd.concat(frames, ignore_index=True).to_csv(dst, index=False)
        assert validate_file(dst, expected_cycles=30) == [], '30-cycle synthetic protocol shape'
        assert validate_file(dst), '30-cycle file must not silently pass legacy 5-cycle gate'
        partial = pd.concat(frames[:-1], ignore_index=True)
        partial.to_csv(dst, index=False)
        assert validate_file(dst, expected_cycles=30), '29-cycle incomplete must fail'
    print('TAKE30_SCHEMA_NEGATIVE_AND_HISTORICAL_REGRESSION_PASS')


if __name__ == '__main__':
    main()
