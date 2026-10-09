"""Regresi pemfilteran data bench dari grafik sensor/origin (tanpa menulis PNG)."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib

import pandas as pd

import plot_sensor_pattern


def main() -> int:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        raw = root / "raw"
        raw.mkdir()
        good = raw / "D-GAW_B35.csv"
        good.write_text("canonical", encoding="utf-8")
        bench = raw / "L-MING_B37.csv"
        bench.write_text("bench", encoding="utf-8")
        new = raw / "M-MING_B38.csv"
        new.write_text("not reviewed", encoding="utf-8")
        caw = raw / "M-CAW_B33.csv"
        caw.write_text("clean air even if manifest missing", encoding="utf-8")
        exclusions = root / "exclusions.csv"
        pd.DataFrame([{
            "source_file": bench.name,
            "source_sha256": hashlib.sha256(bench.read_bytes()).hexdigest(),
            "training_eligible": "false",
        }]).to_csv(exclusions, index=False)
        with patch.object(plot_sensor_pattern, "DATA_DIR", raw), \
             patch.object(plot_sensor_pattern, "EXCLUSION_MANIFEST", exclusions):
            assert plot_sensor_pattern.get_csv_files() == [good]
            bench.write_text("changed", encoding="utf-8")
            try:
                plot_sensor_pattern.get_csv_files()
            except ValueError as error:
                assert "Hash data bench" in str(error)
            else:
                raise AssertionError("Perubahan data bench harus ditolak")
    print("STAGE2_PLOT_PROVENANCE_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
