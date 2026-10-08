"""Regression tests for event-vs-sensor acquisition payload handling."""

from __future__ import annotations

import pandas as pd

from acquisition_schema import (
    ADC_COLS,
    CSV_COLUMNS,
    is_sensor_payload,
    sensor_row_from_payload,
)
from lcd_acquisition_service import AcquisitionService
from validate_acquisition import classify_rows


def make_sensor_payload() -> dict:
    payload = {
        "phase": "collecting",
        "cycle": 3,
        "sample_idx": 2,
        "timestamp": 123456,
        "temperature_c": 27.5,
        "humidity_rh": 61.2,
    }
    for index, column in enumerate(ADC_COLS, start=1):
        payload[column] = 1000 + index
    return payload


def main() -> int:
    phase_change = {
        "event": "PHASE_CHANGE",
        "cycle": 3,
        "phase": "collecting",
    }
    assert not is_sensor_payload(phase_change)

    unknown_event = {
        "event": "FUTURE_EVENT",
        "cycle": 3,
        "phase": "collecting",
    }
    assert not is_sensor_payload(unknown_event)

    sensor = make_sensor_payload()
    assert is_sensor_payload(sensor)

    # Environment data may legitimately be unavailable for one sample.
    env_missing = dict(sensor, temperature_c=None, humidity_rh=None)
    assert is_sensor_payload(env_missing)

    missing_adc = dict(sensor)
    missing_adc["adc_mq3"] = None
    assert not is_sensor_payload(missing_adc)

    row = sensor_row_from_payload(
        env_missing,
        sample_id="D-GAW",
        roast_level="dark",
        origin="Arabika Gayo Wine",
        batch_id="B99",
    )
    assert set(row) == set(CSV_COLUMNS)
    assert row["timestamp"] == 123456
    assert row["run_id"] == 3
    assert row["phase"] == "collecting"
    assert row["temperature"] is None
    assert row["humidity"] is None
    assert all(row[column] is not None for column in ADC_COLS)

    # Historical PHASE_CHANGE-style CSV row must classify as metadata-only,
    # not as a partial or valid sensor row.
    sensor_csv_row = {column: row.get(column) for column in CSV_COLUMNS}
    event_csv_row = {
        column: None
        for column in CSV_COLUMNS
    }
    event_csv_row.update(
        {
            "sample_id": "D-GAW",
            "roast_level": "dark",
            "origin": "Arabika Gayo Wine",
            "batch_id": "B99",
            "run_id": 3,
            "phase": "collecting",
        }
    )
    df = pd.DataFrame([sensor_csv_row, event_csv_row], columns=CSV_COLUMNS)
    valid, metadata, partial = classify_rows(df)
    assert valid.tolist() == [True, False]
    assert metadata.tolist() == [False, True]
    assert partial.tolist() == [False, False]

    # Service-level regression: PHASE_CHANGE must not reach write_sensor().
    class FakeLogger:
        def debug(self, *_args, **_kwargs):
            pass

    class FakeSession:
        def __init__(self):
            self.writes = 0

        def write_sensor(self, _data):
            self.writes += 1

    service = AcquisitionService(
        port="TEST",
        baud=115200,
        reconnect_s=0.1,
        logger=FakeLogger(),
    )
    fake_session = FakeSession()
    service.session = fake_session
    service.handle_event(phase_change)
    assert fake_session.writes == 0
    service.handle_event(sensor)
    assert fake_session.writes == 1

    print("ACQUISITION_PAYLOAD_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
