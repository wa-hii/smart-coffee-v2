#!/usr/bin/env python3
"""Crash-resilient 30-cycle labeled Take Data storage for the RF30 Pi UART.

One consumer owns the FT232 serial. This module never opens a serial port,
transmits commands, controls actuators, calibrates sensors or loads an ML model.
Incomplete/aborted streams are quarantined, not published as valid training.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

from rf30_pi_result_bridge import BUILD_ID, strict_json
from roast_rf30_pi_inference import ADC_COLUMNS

ORIGINS = frozenset(
    ("MING", "MAN", "RAT", "GAY", "MER", "TEM", "CAT",
     "GAW", "TIM", "BAR", "MUK", "CAW", "GRB", "TOR"))
ROASTS = {"L": "light", "M": "medium", "D": "dark"}
SAMPLE_RE = re.compile(r"^([LMD])-([A-Z]{3,4})$")
BATCH_RE = re.compile(r"^B([0-9]{2,4})$")
FIELDS = (
    "timestamp", "sample_id", "roast_level", "origin", "batch_id",
    "run_id", "phase", "sample_idx", *ADC_COLUMNS, "temperature", "humidity"
)
MAX_ROWS = 900
MAX_IDLE_S = 12.0
MAX_PARTIAL_BYTES = 1_500_000


class LabeledDataError(ValueError):
    pass


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def _strict_int(value, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise LabeledDataError("invalid_" + name)
    return value


def _numeric_or_empty(frame: dict, key: str, low: float, high: float):
    val = frame.get(key)
    if val is None:
        return ""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise LabeledDataError("invalid_" + key)
    if not math.isfinite(val) or not low <= val <= high:
        raise LabeledDataError("invalid_" + key)
    return val


def validate_labeled_start(frame: dict) -> dict:
    if (frame.get("event") != "ACQ_START" or
            frame.get("mode") != "labeled_data" or
            frame.get("fw_build_id") != BUILD_ID or
            frame.get("cycles_total") != 30 or
            frame.get("purge_s") != 25 or
            frame.get("collect_s") != 5 or
            frame.get("total_samples_expected") != 900 or
            "ai_session_token" in frame):
        raise LabeledDataError("labeled_data_firmware_contract_mismatch")
    sample = frame.get("sample_id")
    match = SAMPLE_RE.fullmatch(sample) if isinstance(sample, str) else None
    if match is None or match.group(2) not in ORIGINS:
        raise LabeledDataError("invalid_sample_id")
    prefix, origin = match.groups()
    if frame.get("origin_code") != origin or frame.get("roast_level") != ROASTS[prefix]:
        raise LabeledDataError("label_metadata_inconsistent")
    batch = frame.get("batch_id")
    batch_match = BATCH_RE.fullmatch(batch) if isinstance(batch, str) else None
    if batch_match is None or not 1 <= int(batch_match.group(1)) <= 9999:
        raise LabeledDataError("invalid_batch_id")
    expected_filename = f"{sample}_{batch}.csv"
    if frame.get("filename") != expected_filename:
        raise LabeledDataError("labeled_filename_mismatch")
    return {
        "sample_id": sample, "roast_level": ROASTS[prefix],
        "origin": origin, "origin_code": origin, "batch_id": batch,
        "firmware_filename": expected_filename, "fw_build_id": BUILD_ID,
        "total_samples_expected": 900, "cycles": 30,
        "start_recorded_utc": datetime.now(timezone.utc).isoformat(),
    }


def _unique_path(directory: Path, filename: str) -> Path:
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    first = directory / filename
    if not first.exists():
        return first
    for _ in range(5):
        next_path = directory / f"{stem}_{_utc_stamp()}_{uuid.uuid4().hex[:8]}{suffix}"
        if not next_path.exists():
            return next_path
    raise FileExistsError("cannot_reserve_unique_csv_path")


class LabeledTakeRecorder:
    """Single labeled-data session, one stage file, no guessed/repaired rows."""

    def __init__(self, root: Path):
        self.root = root
        self.incoming = root / ".incoming"
        self.incomplete = root / "incomplete"
        self.meta = None
        self.active = False
        self.rows = 0
        self.last_timestamp = -1
        self.temperature_missing = 0
        self.humidity_missing = 0
        self.last_activity = time.monotonic()
        self.part_path = None
        self._file = None
        self._writer = None
        self._capture_hash = None
        self._mkdir()

    def _mkdir(self):
        for directory in (self.root, self.incoming, self.incomplete):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(directory, 0o700)

    def recover_stale_partials(self) -> int:
        """Call at service startup BEFORE UART open; never overwrite prior CSVs."""
        if self.active:
            raise RuntimeError("cannot_recover_during_active_session")
        recovered = 0
        for path in self.incoming.glob("*.partial.csv"):
            if not path.is_file() or path.is_symlink():
                continue
            dest = _unique_path(self.incomplete, path.stem + "_BOOT_RECOVERED.csv")
            path.rename(dest)
            recovered += 1
        return recovered

    def start(self, frame: dict) -> dict:
        meta = validate_labeled_start(frame)
        if self.active:
            self.abort("new_start_during_prior_acquisition")
        self._mkdir()
        self.meta = meta
        self.rows = 0
        self.last_timestamp = -1
        self.temperature_missing = 0
        self.humidity_missing = 0
        self.last_activity = time.monotonic()
        base = Path(meta["firmware_filename"]).stem
        name = f"{base}_{_utc_stamp()}_{uuid.uuid4().hex[:8]}.partial.csv"
        self.part_path = self.incoming / name
        self._file = self.part_path.open("x", newline="", encoding="utf8")
        os.chmod(self.part_path, 0o600)
        self._writer = csv.DictWriter(self._file, fieldnames=FIELDS)
        self._writer.writeheader()
        self._file.flush()
        os.fsync(self._file.fileno())
        self.active = True
        return {"status": "LABELED_CAPTURE_STARTED", **meta}

    def _close(self):
        if self._file is not None:
            self._file.flush()
            os.fsync(self._file.fileno())
            self._file.close()
            self._file = None
            self._writer = None

    def abort(self, reason: str) -> dict:
        if not self.active:
            return {"status": "LABELED_NOT_ACTIVE"}
        previous_rows = self.rows
        part = self.part_path
        meta = dict(self.meta)
        self._close()
        dest = _unique_path(
            self.incomplete, f"{meta['sample_id']}_{meta['batch_id']}_INCOMPLETE.csv")
        part.rename(dest)
        summary = {
            **meta, "status": "INCOMPLETE_NOT_FOR_TRAINING",
            "reason": reason[:140], "rows": previous_rows,
            "csv_filename": dest.name,
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
        }
        (self.incomplete / (dest.name + ".json")).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf8")
        self.active = False
        self.meta = None
        return {"status": "LABELED_INCOMPLETE_QUARANTINED",
                "rows": previous_rows, "reason": reason, "path": str(dest)}

    def _sensor_row(self, frame: dict) -> dict:
        index = self.rows
        if index >= MAX_ROWS:
            raise LabeledDataError("too_many_sensor_rows")
        cycle = index // 30 + 1
        offset = index % 30
        phase = "purging" if offset < 25 else "collecting"
        sample_idx = offset + 1 if offset < 25 else offset - 24
        if (frame.get("event") is not None or
                frame.get("cycle") != cycle or
                frame.get("phase") != phase or
                frame.get("sample_idx") != sample_idx):
            raise LabeledDataError("wrong_cycle_phase_or_sample_idx")
        timestamp = _strict_int(frame.get("timestamp"), "timestamp", 0, 0xFFFFFFFF)
        if timestamp <= self.last_timestamp:
            raise LabeledDataError("non_monotonic_timestamp")
        values = {name: _strict_int(frame.get(name), name, 0, 32767)
                  for name in ADC_COLUMNS}
        temperature = _numeric_or_empty(frame, "temperature_c", -60, 125)
        humidity = _numeric_or_empty(frame, "humidity_rh", 0, 100)
        self.last_timestamp = timestamp
        return {
            "timestamp": timestamp, "sample_id": self.meta["sample_id"],
            "roast_level": self.meta["roast_level"],
            "origin": self.meta["origin"], "batch_id": self.meta["batch_id"],
            "run_id": cycle, "phase": phase, "sample_idx": sample_idx,
            **values, "temperature": temperature, "humidity": humidity,
        }

    def receive(self, raw: bytes) -> dict:
        if not self.active:
            return {"status": "LABELED_NOT_ACTIVE"}
        self.last_activity = time.monotonic()
        try:
            if len(raw) > 4096 or b"\x00" in raw:
                raise LabeledDataError("invalid_serial_frame")
            frame = strict_json(raw.decode("utf8"))
            event = frame.get("event")
            if event in ("ACQ_STOP", "ACQ_TIMING_FAULT", "FW_HELLO"):
                return self.abort("firmware_" + event.lower())
            if event == "ACQ_START":
                return self.abort("duplicate_start")
            if event == "ACQ_COMPLETE":
                if (frame.get("cycles") != 30 or
                        frame.get("total_samples") != 900 or self.rows != 900):
                    return self.abort("incomplete_or_invalid_completion")
                return self.finish()
            if event in ("PHASE_CHANGE", "ACQ_PAUSE", "ACQ_RESUME"):
                return {"status": "LABELED_AUX_EVENT", "event": event}
            if event is not None:
                raise LabeledDataError("unexpected_event_" + str(event)[:40])
            if "phase" not in frame and "sample_idx" not in frame:
                return {"status": "LABELED_IGNORED_NON_SENSOR_STATUS"}
            row = self._sensor_row(frame)
            self._writer.writerow(row)
            self.rows += 1
            if row["temperature"] == "":
                self.temperature_missing += 1
            if row["humidity"] == "":
                self.humidity_missing += 1
            # Persist all samples even if power is unexpectedly lost; 1Hz.
            self._file.flush()
            os.fsync(self._file.fileno())
            if self.part_path.stat().st_size > MAX_PARTIAL_BYTES:
                raise LabeledDataError("partial_csv_size_limit_exceeded")
            return {"status": "LABELED_SAMPLE_ACCEPTED", "rows": self.rows}
        except (ValueError, UnicodeError, KeyError, TypeError, OSError) as exc:
            return self.abort(type(exc).__name__ + ":" + str(exc)[:120])

    def finish(self) -> dict:
        if not self.active or self.rows != 900:
            raise LabeledDataError("finish_requires_900_samples")
        finished_meta = dict(self.meta)
        self._close()
        # Unique private publication with no overwrite (hardlink O_EXCL).
        final = _unique_path(self.root, self.meta["firmware_filename"])
        for _ in range(6):
            try:
                os.link(self.part_path, final)
                break
            except FileExistsError:
                final = _unique_path(self.root, self.meta["firmware_filename"])
        else:
            return self.abort("cannot_publish_unique_csv")
        self.part_path.unlink()
        data_sha = sha256(final.read_bytes()).hexdigest()
        self.active = False
        self.meta = None
        summary = {
            **finished_meta,
            "status": "COMPLETE_30_CYCLES_900_SAMPLES",
            "rows": 900, "csv_filename": final.name,
            "csv_sha256": data_sha,
            "temperature_missing_rows": self.temperature_missing,
            "humidity_missing_rows": self.humidity_missing,
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
        }
        sidecar = self.root / (final.name + ".json")
        with sidecar.open("x", encoding="utf8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.active = False
        self.meta = None
        return {"status": "LABELED_CSV_SAVED_900_VALID",
                "path": str(final), "rows": 900, "sha256": data_sha}

    def check_timeout(self, now: float | None = None) -> dict | None:
        if self.active and (time.monotonic() if now is None else now) - self.last_activity > MAX_IDLE_S:
            return self.abort("sensor_uart_idle_timeout")
        return None
