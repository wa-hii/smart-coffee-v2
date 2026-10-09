"""Regresi QA pasif, hanya membuat fixture di direktori sementara."""

from pathlib import Path
from tempfile import TemporaryDirectory

from bench_stage1_passive_qa import inspect_completed_csv
from test_acquisition_integrity import make_complete_run


def main() -> int:
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
