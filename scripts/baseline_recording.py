"""Fail-closed baseline acquisition from the Nextion Calibrate button.

Never overwrites any coffee CSV or EEPROM; publishes only 60 verified samples.
"""
from __future__ import annotations

import csv
import math
import os
from pathlib import Path
import time
import uuid

from acquisition_schema import ADC_COLS, _integer_in_range, environment_values

BASELINE_COLS = ["timestamp", "sample_idx", *ADC_COLS, "temperature", "humidity"]
BASELINE_SAMPLES = 60


class BaselineRecording:
    def __init__(self, root: Path, event: dict):
        if (event.get("protocol") != "clean_air_adc.v1"
                or type(event.get("target_samples")) is not int
                or event["target_samples"] != BASELINE_SAMPLES
                or event.get("interval_ms") != 1000
                or event.get("eeprom_r0_modified") is not False):
            raise ValueError("Unsupported or unsafe BASELINE_START contract")
        self.root = root
        self.build_id = str(event.get("fw_build_id") or "UNKNOWN")
        self.uuid = uuid.uuid4().hex
        self.rows = 0
        self.last_timestamp = None
        self.filename = (
            "BASELINE_" + time.strftime("%Y%m%d_%H%M%S") + "_"
            + self.uuid[:12] + ".csv"
        )
        self.incoming = root / ".incoming"
        self.incomplete = root / "incomplete"
        self.incoming.mkdir(parents=True, exist_ok=True)
        self.incomplete.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self.partial = self.incoming / (self.uuid + ".partial.csv")
        self.final = root / self.filename
        self.f = self.partial.open("x", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.f, fieldnames=BASELINE_COLS)
        self.writer.writeheader()
        self.flush()

    def flush(self):
        self.f.flush()
        os.fsync(self.f.fileno())

    def add(self, data: dict):
        if data.get("event") != "BASELINE_SAMPLE" or data.get("phase") != "baseline":
            raise ValueError("Unexpected baseline sample frame")
        if data.get("cycle") != 0 or not _integer_in_range(data.get("timestamp"), 0, 0xFFFFFFFF):
            raise ValueError("Invalid baseline cycle or timestamp")
        if type(data.get("sample_idx")) is not int or data["sample_idx"] != self.rows + 1:
            raise ValueError("Baseline sample index missing, duplicated, or out of order")
        if self.rows >= BASELINE_SAMPLES:
            raise ValueError("Too many baseline samples")
        timestamp = data["timestamp"]
        if self.last_timestamp is not None:
            diff = timestamp - self.last_timestamp
            if diff < 900 or diff > 1100:
                raise ValueError(f"Baseline sample interval invalid: {diff} ms")
        row = {"timestamp": timestamp, "sample_idx": self.rows + 1}
        for adc in ADC_COLS:
            if not _integer_in_range(data.get(adc), 1, 32766):
                raise ValueError(f"Invalid ADC: {adc}")
            row[adc] = data[adc]
        temp, rh = environment_values(data)
        if (type(temp) not in (float, int) or type(rh) not in (float, int)
                or not (math.isfinite(temp) and -40 <= temp <= 125)
                or not (math.isfinite(rh) and 0 <= rh <= 100)):
            raise ValueError("Temperature/humidity missing or implausible")
        row["temperature"], row["humidity"] = temp, rh
        self.writer.writerow(row)
        self.flush()
        self.last_timestamp = timestamp
        self.rows += 1

    def complete(self, event: dict) -> Path:
        if (event.get("event") != "BASELINE_COMPLETE"
                or type(event.get("samples")) is not int
                or event["samples"] != BASELINE_SAMPLES
                or self.rows != BASELINE_SAMPLES):
            raise ValueError("Baseline incomplete or completion count mismatch")
        self.flush()
        self.f.close()
        # No-clobber publish: a unique name, and hard link fails if it exists.
        os.link(self.partial, self.final)
        self.partial.unlink()
        return self.final

    def preserve_incomplete(self, reason: str) -> Path:
        if not self.f.closed:
            self.flush()
            self.f.close()
        if self.partial.exists():
            target = self.incomplete / (self.uuid + "_INCOMPLETE.csv")
            os.link(self.partial, target)
            self.partial.unlink()
            return target
        return self.incomplete / (self.uuid + "_NOT_SAVED.txt")
