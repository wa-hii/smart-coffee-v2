"""Regresi QA pasif, hanya membuat fixture di direktori sementara."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from bench_stage1_passive_qa import inspect_completed_csv
from test_acquisition_integrity import make_complete_run


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = pd.read_csv(root / "data/analysis/bench_only_exclusions.csv")
    assert set(manifest["source_file"]) == {
        "L-MING_B37.csv", "M-MING_B37.csv"
    }
    assert set(manifest["training_eligible"].astype(str).str.lower()) == {"false"}
    for entry in manifest.itertuples():
        raw = root / "data/raw" / entry.source_file
        if raw.is_file():
            assert hashlib.sha256(raw.read_bytes()).hexdigest() == entry.source_sha256

    with TemporaryDirectory() as temp:
        path = Path(temp) / "D-GAW_B99.csv"
        valid = make_complete_run()
        valid.to_csv(path, index=False)
        info = inspect_completed_csv(path)
        assert not info["errors"], info["errors"]
        assert info["rows"] == 150
        assert len(info["cycles"]) == 10

        missing = valid.drop(index=[0])
        missing.to_csv(path, index=False)
        assert inspect_completed_csv(path)["errors"]

        wrong = valid.copy()
        wrong.loc[1, "timestamp"] = wrong.loc[0, "timestamp"] + 500
        wrong.to_csv(path, index=False)
        assert any(
            "Interval timestamp" in issue
            for issue in inspect_completed_csv(path)["errors"]
        )

        # 6 sampel collecting dapat berurutan dan tetap sah sebagai angka,
        # tetapi tidak lulus target ketat 5 sampel dalam SOP bench tanpa pause.
        extra = valid.copy()
        idx = int(extra.index[(extra["run_id"] == 1)
                              & (extra["phase"] == "collecting")][-1])
        row = extra.loc[[idx]].copy()
        row.loc[:, "sample_idx"] = 6
        extra = pd.concat([extra.iloc[:idx+1], row,
                           extra.iloc[idx+1:]], ignore_index=True)
        extra.loc[idx+1:, "timestamp"] += 1000
        extra.to_csv(path, index=False)
        issues = inspect_completed_csv(path)["errors"]
        assert any("Jumlah sampel" in issue for issue in issues), issues
        assert not any("sample_idx tidak kontigu" in issue for issue in issues), issues

        bad_dir = Path(temp) / "incomplete"
        bad_dir.mkdir()
        bad_file = bad_dir / "D-GAW_B99.partial.csv"
        valid.to_csv(bad_file, index=False)
        try:
            inspect_completed_csv(bad_file)
        except ValueError:
            pass
        else:
            raise AssertionError("Wajib menolak staging/incomplete")

        malformed = valid.drop(columns=["adc_mq3"])
        malformed.to_csv(path, index=False)
        try:
            inspect_completed_csv(path)
        except ValueError:
            pass
        else:
            raise AssertionError("Wajib menolak skema data tanpa sensor")

    print("BENCH_STAGE1_PASSIVE_QA_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
