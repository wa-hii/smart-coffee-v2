"""Offline feature extraction regression; synthetic data and no real CSV edits."""

import hashlib
import tempfile
from pathlib import Path

import pandas as pd

from acquisition_schema import CSV_COLUMNS
from extract_b32_features import extract_file
from test_acquisition_integrity import make_complete_run


def main() -> int:
    with tempfile.TemporaryDirectory() as dirname:
        path = Path(dirname) / "D-GAW_B99.csv"
        synthetic = make_complete_run()
        synthetic.to_csv(path, index=False)
        original = hashlib.sha256(path.read_bytes()).hexdigest()
        first = extract_file(path)
        second = extract_file(path)
        assert first == second
        assert first["n_cycles"] == 5
        assert len([key for key in first if key.startswith("f_")]) == 62
        assert first["source_sha256"] == original
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original

        event = {column: None for column in CSV_COLUMNS}
        event.update(sample_id="D-GAW", roast_level="dark",
                     origin="Arabika Gayo Wine", batch_id="B99",
                     run_id=3, phase="collecting")
        with_event = pd.concat([synthetic, pd.DataFrame([event])],
                               ignore_index=True)
        with_event.to_csv(path, index=False)
        third = extract_file(path)
        assert {key: value for key, value in first.items()
                if key not in ("source_sha256",)} == {
                    key: value for key, value in third.items()
                    if key not in ("source_sha256",)
                }

        broken = synthetic.copy()
        broken.loc[0, "adc_mq3"] = None
        broken.to_csv(path, index=False)
        try:
            extract_file(path)
        except ValueError:
            pass
        else:
            raise AssertionError("partial sensor row must reject extraction")

    print("B32_FEATURE_PIPELINE_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
