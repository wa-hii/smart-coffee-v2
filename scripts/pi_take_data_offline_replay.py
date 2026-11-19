#!/usr/bin/env python3
"""Replay 900 real sensor frames to TEST the CSV writer, not to label coffee.

Input is a prior AI Test .ndjson; its roast/origin ground truth is UNKNOWN.
Inject synthetic L-TOR/B99 labels ONLY inside a temporary directory,
which is deleted after QA. NEVER produce a training dataset from this replay.
No serial open / no model deserialize / no Raspberry Pi hardware commands.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import tempfile

from rf500_pi_persistent_listener import PersistentHandler
from rf30_pi_result_bridge import strict_json


def replay(path: Path):
    records = path.read_bytes().splitlines(keepends=True)
    if len(records) < 902 or len(records) > 1100:
        raise ValueError("invalid_recorded_firmware_stream_count")
    start = strict_json(records[0].decode("utf8"))
    if start.get("event") != "ACQ_START" or start.get("mode") != "ai_test":
        raise ValueError("requires_original_complete_ai_test_capture")
    start.pop("ai_session_token", None)
    start.update({
        "mode": "labeled_data",
        "sample_id": "L-TOR", "roast_level": "light",
        "origin_code": "TOR", "batch_id": "B99",
        "filename": "L-TOR_B99.csv",
        "total_samples_expected": 900,
    })
    original = records[1:]
    with tempfile.TemporaryDirectory(prefix="take_data_pi_offline_") as tmp:
        root = Path(tmp)
        model_calls = []
        handler = PersistentHandler(
            predictor=lambda _: model_calls.append("FORBIDDEN"),
            archive_dir=root / "ai",
            take_data_dir=root / "data/raw")
        command, status = handler.receive((json.dumps(start) + "\n").encode())
        if command is not None or status["status"] != "LABELED_CAPTURE_STARTED":
            raise AssertionError("Labeled start did not enter capture")
        for raw in original:
            command, status = handler.receive(raw)
            if command is not None:
                raise AssertionError("unexpected UART result from labeled data")
        if status["status"] != "LABELED_CSV_SAVED_900_VALID":
            raise AssertionError("recording did not validate and save")
        files = list((root / "data/raw").glob("*.csv"))
        if len(files) != 1:
            raise AssertionError("exactly one test CSV expected")
        with files[0].open(newline="", encoding="utf8") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 900 or model_calls:
            raise AssertionError("invalid rows or forbidden inference")
        sidecar = json.loads((root / "data/raw" / (files[0].name + ".json")).read_text())
        result = {
            "status": "PI_TAKE_DATA_REAL_SENSOR_REPLAY_OFFLINE_PASS",
            "rows": len(rows), "cycles": 30,
            "synthetic_training_labels_saved": False,
            "temporary_files_deleted_on_exit": True,
            "model_invoked": bool(model_calls),
            "uart_opened": False, "uart_tx": False,
            "sensor_csv_sha256": sidecar["csv_sha256"],
        }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--recording", type=Path, required=True)
    replay(cli.parse_args().recording)
