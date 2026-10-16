"""Offline end-to-end baseline protocol and negative QC checks (no serial)."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pandas as pd

from acquisition_schema import ADC_COLS
from lcd_acquisition_service import AcquisitionService

START = dict(event="BASELINE_START", protocol="clean_air_adc.v1",
             target_samples=60, interval_ms=1000, eeprom_r0_modified=False)
COMPLETE = dict(event="BASELINE_COMPLETE", samples=60)


def sample(n: int):
    return dict(event="BASELINE_SAMPLE", phase="baseline", cycle=0,
                sample_idx=n, timestamp=100000+n*1000,
                temperature_c=29.2, humidity_rh=55.6,
                **{channel: 8000+i+n for i, channel in enumerate(ADC_COLS)})


def service():
    return AcquisitionService("MOCK", 115200, 1, Mock())


def main():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        with patch("lcd_acquisition_service.BASELINE_DIR", root):
            s = service()
            s.handle_event(START)
            assert s.baseline is not None
            for n in range(1, 61):
                s.handle_event(sample(n))
            s.handle_event(COMPLETE)
            assert s.baseline is None
            finals = list(root.glob("BASELINE_*.csv"))
            assert len(finals) == 1
            assert finals[0].with_suffix(".baseline_qc.json").exists()
            df = pd.read_csv(finals[0])
            assert df.shape == (60, 14)
            assert df.sample_idx.tolist() == list(range(1, 61))
            assert df.timestamp.diff().dropna().eq(1000).all()
            assert set(ADC_COLS).issubset(df.columns)
            from baseline_quality import inspect_baseline
            summary = inspect_baseline(finals[0])
            assert len(summary["sensor_b0"]) == 10
            assert summary["status"] == "CAPTURE_COMPLETE_AIR_QUALITY_UNVERIFIED"

            # 59 samples cannot be published as a completed baseline.
            s.handle_event(START)
            for n in range(1, 60):
                s.handle_event(sample(n))
            s.handle_event(COMPLETE)
            assert len(list(root.glob("BASELINE_*.csv"))) == 1
            assert list((root/"incomplete").glob("*_INCOMPLETE.csv"))

            # Gap/duplicate/sample corruption must immediately quarantine.
            for corrupt in (dict(sample(2)), {**sample(1), "adc_mq8": None},
                            {**sample(1), "temperature_c": None},
                            {**sample(1), "adc_mq3": 32767}):
                s.handle_event(START)
                s.handle_event(corrupt)
                assert s.baseline is None
                assert len(list(root.glob("BASELINE_*.csv"))) == 1

            # Cancellation cannot publish a valid baseline.
            s.handle_event(START)
            s.handle_event(sample(1))
            s.handle_event({"event": "BASELINE_ABORT", "samples": 1})
            assert s.baseline is None
            assert len(list(root.glob("BASELINE_*.csv"))) == 1

            # Repeated or invalid START must not overwrite existing baseline.
            s.handle_event({**START, "eeprom_r0_modified": True})
            assert s.baseline is None
            assert len(list(root.glob("BASELINE_*.csv"))) == 1
    print("BASELINE60_LISTENER_REGRESSION_PASS")


if __name__ == "__main__":
    main()
